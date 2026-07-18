import os
import re
import uuid
from datetime import datetime
from typing import List, Optional

PAGE_MARKER = re.compile(r"\[Page (\d+)\]")

from fastapi import UploadFile
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_mistralai import MistralAIEmbeddings
from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.database import open_db as SessionLocal, UploadedDocument
from app.services.model_service import resolve_ocr_model
from app.services.ocr_service import extract_pdf_with_ocr
from app.services.memory_service import memory_service

settings = get_settings()
EMBED_BATCH = 40


class DocumentService:
    def __init__(self):
        os.makedirs(settings.upload_dir, exist_ok=True)
        os.makedirs(settings.chroma_persist_dir, exist_ok=True)
        self.embeddings = MistralAIEmbeddings(
            model="mistral-embed",
            mistral_api_key=settings.mistral_api_key,
        )
        self.vectorstore = Chroma(
            collection_name="document_chunks",
            embedding_function=self.embeddings,
            persist_directory=settings.chroma_persist_dir,
        )
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.doc_chunk_size,
            chunk_overlap=settings.doc_chunk_overlap,
            length_function=len,
        )

    def _session_upload_dir(self, session_id: str) -> str:
        path = os.path.join(settings.upload_dir, session_id)
        os.makedirs(path, exist_ok=True)
        return path

    async def save_uploads(
        self, db: Session, session_id: str, files: List[UploadFile]
    ) -> List[UploadedDocument]:
        records = []
        upload_dir = self._session_upload_dir(session_id)

        for file in files:
            if not file.filename or not file.filename.lower().endswith(".pdf"):
                continue

            doc_id = str(uuid.uuid4())
            dest = os.path.join(upload_dir, f"{doc_id}.pdf")

            content = await file.read()
            with open(dest, "wb") as f:
                f.write(content)

            record = UploadedDocument(
                id=doc_id,
                session_id=session_id,
                filename=file.filename,
                file_size=len(content),
                status="pending",
                created_at=datetime.utcnow(),
            )
            db.add(record)
            records.append(record)

        db.commit()
        for r in records:
            db.refresh(r)
        return records

    def list_documents(self, db: Session, session_id: str) -> List[UploadedDocument]:
        return (
            db.query(UploadedDocument)
            .filter(
                UploadedDocument.session_id == session_id,
                UploadedDocument.status != "removed",
            )
            .order_by(UploadedDocument.created_at.desc())
            .all()
        )

    def get_document(self, db: Session, doc_id: str) -> Optional[UploadedDocument]:
        return db.query(UploadedDocument).filter(UploadedDocument.id == doc_id).first()

    def _page_range_from_chunk(self, chunk: str) -> tuple[int, int]:
        pages = [int(m.group(1)) for m in PAGE_MARKER.finditer(chunk)]
        if not pages:
            return 1, 1
        return min(pages), max(pages)

    def _snippet_from_chunk(self, chunk: str, max_len: int = 220) -> str:
        text = PAGE_MARKER.sub("", chunk).strip()
        text = " ".join(text.split())
        if len(text) <= max_len:
            return text
        trimmed = text[:max_len].rsplit(" ", 1)[0]
        return f"{trimmed}…"

    def hits_to_citations(self, hits: List[dict]) -> List[dict]:
        citations = []
        for i, hit in enumerate(hits, 1):
            page_start = hit.get("page_start", 1)
            page_end = hit.get("page_end", page_start)
            citations.append(
                {
                    "id": i,
                    "document_id": hit.get("document_id", ""),
                    "filename": hit.get("filename", "unknown"),
                    "chunk_index": hit.get("chunk_index", 0),
                    "page": page_start,
                    "page_end": page_end,
                    "snippet": hit.get("snippet", ""),
                    "content": hit.get("content", ""),
                }
            )
        return citations

    def document_file_path(self, session_id: str, doc_id: str) -> str:
        return os.path.join(self._session_upload_dir(session_id), f"{doc_id}.pdf")

    def _extract_pdf_text(self, path: str, ocr_model: str = "auto") -> tuple[str, int, str]:
        """Returns (text, page_count, extraction_method)."""
        reader = PdfReader(path)
        pages = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if text.strip():
                pages.append(f"[Page {i + 1}]\n{text}")
        pypdf_text = "\n\n".join(pages)
        page_count = len(reader.pages)

        use_ocr_always = ocr_model and ocr_model != "auto"
        needs_ocr = use_ocr_always or len(pypdf_text.strip()) < 200

        if needs_ocr:
            try:
                model_id = resolve_ocr_model(ocr_model)
                ocr_text, ocr_pages = extract_pdf_with_ocr(path, model_id)
                if ocr_text.strip():
                    return ocr_text, ocr_pages, f"mistral-ocr ({model_id})"
            except Exception:
                if use_ocr_always:
                    raise

        if pypdf_text.strip():
            return pypdf_text, page_count, "pypdf"
        raise ValueError("No extractable text in PDF — try enabling Mistral OCR in Settings")

    def process_document(self, doc_id: str, ocr_model: str = "auto") -> None:
        db = SessionLocal()
        try:
            doc = self.get_document(db, doc_id)
            if not doc:
                return

            doc.status = "processing"
            db.commit()

            path = os.path.join(
                self._session_upload_dir(doc.session_id), f"{doc.id}.pdf"
            )
            if not os.path.exists(path):
                doc.status = "failed"
                doc.error_message = "File not found on disk"
                db.commit()
                return

            full_text, page_count, method = self._extract_pdf_text(path, ocr_model)
            if not full_text.strip():
                doc.status = "failed"
                doc.error_message = "No extractable text in PDF"
                db.commit()
                return

            raw_chunks = self.splitter.split_text(full_text)
            lc_docs = []
            for idx, chunk in enumerate(raw_chunks):
                page_start, page_end = self._page_range_from_chunk(chunk)
                lc_docs.append(
                    Document(
                        page_content=chunk,
                        metadata={
                            "session_id": doc.session_id,
                            "document_id": doc.id,
                            "filename": doc.filename,
                            "chunk_index": idx,
                            "page_start": page_start,
                            "page_end": page_end,
                        },
                    )
                )

            for i in range(0, len(lc_docs), EMBED_BATCH):
                batch = lc_docs[i : i + EMBED_BATCH]
                self.vectorstore.add_documents(batch)

            doc.status = "ready"
            doc.page_count = page_count
            doc.chunk_count = len(lc_docs)
            doc.processed_at = datetime.utcnow()
            doc.error_message = ""
            db.commit()
        except Exception as e:
            doc = self.get_document(db, doc_id)
            if doc:
                doc.status = "failed"
                doc.error_message = str(e)[:500]
                db.commit()
        finally:
            db.close()

    def process_pending_batch(self, doc_ids: List[str], ocr_model: str = "auto") -> None:
        for doc_id in doc_ids:
            self.process_document(doc_id, ocr_model)

    def get_ready_document_ids(self, db: Session, session_id: str) -> List[str]:
        rows = (
            db.query(UploadedDocument.id)
            .filter(
                UploadedDocument.session_id == session_id,
                UploadedDocument.status == "ready",
            )
            .all()
        )
        return [row[0] for row in rows]

    def search(
        self, db: Session, session_id: str, query: str, k: Optional[int] = None
    ) -> List[dict]:
        doc_ids = self.get_ready_document_ids(db, session_id)
        if not doc_ids:
            return []

        k = k or settings.doc_retrieval_k
        where_filter = {
            "$and": [
                {"session_id": session_id},
                {"document_id": {"$in": doc_ids}},
            ]
        }
        results = self.vectorstore.similarity_search(
            query,
            k=k,
            filter=where_filter,
        )
        hits = []
        for doc in results:
            page_start = int(doc.metadata.get("page_start", 1))
            page_end = int(doc.metadata.get("page_end", page_start))
            content = doc.page_content
            hits.append(
                {
                    "content": content,
                    "document_id": doc.metadata.get("document_id", ""),
                    "filename": doc.metadata.get("filename", "unknown"),
                    "chunk_index": doc.metadata.get("chunk_index", 0),
                    "page_start": page_start,
                    "page_end": page_end,
                    "snippet": self._snippet_from_chunk(content),
                }
            )
        return hits

    def delete_document(self, db: Session, doc_id: str) -> bool:
        doc = self.get_document(db, doc_id)
        if not doc or doc.status == "removed":
            return False

        session_id = doc.session_id

        try:
            self.vectorstore._collection.delete(where={"document_id": doc_id})
        except Exception:
            pass

        path = os.path.join(
            self._session_upload_dir(session_id), f"{doc.id}.pdf"
        )
        if os.path.exists(path):
            os.remove(path)

        doc.status = "removed"
        doc.error_message = ""
        db.commit()

        if not self.get_ready_document_ids(db, session_id):
            memory_service.clear_session(session_id)
        return True

    def session_has_ready_docs(self, db: Session, session_id: str) -> bool:
        return (
            db.query(UploadedDocument)
            .filter(
                UploadedDocument.session_id == session_id,
                UploadedDocument.status == "ready",
            )
            .count()
            > 0
        )

    def ready_doc_count(self, db: Session, session_id: str) -> int:
        return (
            db.query(UploadedDocument)
            .filter(
                UploadedDocument.session_id == session_id,
                UploadedDocument.status == "ready",
            )
            .count()
        )

    def session_has_removed_docs(self, db: Session, session_id: str) -> bool:
        return (
            db.query(UploadedDocument)
            .filter(
                UploadedDocument.session_id == session_id,
                UploadedDocument.status == "removed",
            )
            .count()
            > 0
        )


document_service = DocumentService()
