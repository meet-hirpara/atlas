import json
import os
import re
import shutil
import uuid
from datetime import datetime
from typing import List, Optional, Tuple
from urllib.parse import urlparse

from git import Repo
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_mistralai import MistralAIEmbeddings
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.database import GithubRepo, open_db as SessionLocal
from app.services.call_graph_parser import CODE_EXTENSIONS, SKIP_DIRS, build_repo_graph
from app.services.llm_service import get_llm

settings = get_settings()
EMBED_BATCH = 40
GITHUB_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?/?$"
)
from app.services.build_mode_service import is_build_request as detect_build_request


def _redact_secrets(text: str, token: str = "") -> str:
    if token:
        text = text.replace(token, "***")
    return re.sub(r"https?://[^@\s/]+@", "https://***@", text)


class GithubRepoService:
    def __init__(self):
        os.makedirs(settings.github_repos_dir, exist_ok=True)
        os.makedirs(settings.chroma_persist_dir, exist_ok=True)
        self.embeddings = MistralAIEmbeddings(
            model="mistral-embed",
            mistral_api_key=settings.mistral_api_key,
        )
        self.vectorstore = Chroma(
            collection_name="github_repo_chunks",
            embedding_function=self.embeddings,
            persist_directory=settings.chroma_persist_dir,
        )
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.doc_chunk_size,
            chunk_overlap=settings.doc_chunk_overlap,
            length_function=len,
        )

    def parse_url(self, url: str) -> Tuple[str, str, str]:
        url = url.strip().rstrip("/")
        m = GITHUB_URL_RE.match(url)
        if not m:
            raise ValueError("Invalid GitHub URL. Use https://github.com/owner/repo")
        owner, name = m.group(1), m.group(2)
        if name.endswith(".git"):
            name = name[:-4]
        return owner, name, f"https://github.com/{owner}/{name}.git"

    def list_repos(self, db: Session, user_id: Optional[str] = None) -> List[GithubRepo]:
        q = db.query(GithubRepo).order_by(GithubRepo.created_at.desc())
        if user_id:
            q = q.filter(GithubRepo.user_id == user_id)
        return q.all()

    def get_repo(
        self, db: Session, repo_id: str, user_id: Optional[str] = None
    ) -> Optional[GithubRepo]:
        q = db.query(GithubRepo).filter(GithubRepo.id == repo_id)
        if user_id:
            q = q.filter(GithubRepo.user_id == user_id)
        return q.first()

    def add_repo(
        self,
        db: Session,
        url: str,
        token: str = "",
        branch: str = "main",
        user_id: Optional[str] = None,
    ) -> GithubRepo:
        owner, name, _clone_url = self.parse_url(url)
        q = db.query(GithubRepo).filter(GithubRepo.owner == owner, GithubRepo.name == name)
        if user_id:
            q = q.filter(GithubRepo.user_id == user_id)
        existing = q.first()
        if existing and existing.status not in ("failed",):
            return existing

        if existing and existing.status == "failed":
            if existing.clone_path and os.path.exists(existing.clone_path):
                shutil.rmtree(existing.clone_path, ignore_errors=True)
            record = existing
            record.url = url.strip()
            record.branch = branch or "main"
            record.status = "pending"
            record.error_message = ""
            record.file_count = 0
            record.chunk_count = 0
            record.graph_json = "{}"
            record.indexed_at = None
            if user_id and not record.user_id:
                record.user_id = user_id
            db.commit()
            db.refresh(record)
            return record

        repo_id = str(uuid.uuid4())
        clone_path = os.path.join(settings.github_repos_dir, repo_id)

        record = GithubRepo(
            id=repo_id,
            user_id=user_id,
            url=url.strip(),
            owner=owner,
            name=name,
            branch=branch or "main",
            status="pending",
            clone_path=clone_path,
            created_at=datetime.utcnow(),
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    def _clone(self, record: GithubRepo, token: str = "") -> None:
        if os.path.exists(record.clone_path):
            shutil.rmtree(record.clone_path, ignore_errors=True)
        os.makedirs(record.clone_path, exist_ok=True)

        clone_url = f"https://github.com/{record.owner}/{record.name}.git"
        if token:
            parsed = urlparse(clone_url)
            clone_url = f"{parsed.scheme}://{token}@{parsed.netloc}{parsed.path}"

        Repo.clone_from(
            clone_url,
            record.clone_path,
            branch=record.branch,
            depth=1,
            single_branch=True,
        )

    def _collect_code_files(self, root: str) -> List[Tuple[str, str]]:
        files: List[Tuple[str, str]] = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fname in filenames:
                ext = os.path.splitext(fname)[1].lower()
                if ext not in CODE_EXTENSIONS:
                    continue
                full = os.path.join(dirpath, fname)
                rel = os.path.relpath(full, root).replace("\\", "/")
                try:
                    with open(full, "r", encoding="utf-8", errors="ignore") as f:
                        files.append((rel, f.read()))
                except OSError:
                    continue
        return files

    def index_repo(self, repo_id: str, token: str = "") -> None:
        db = SessionLocal()
        try:
            claimed = (
                db.query(GithubRepo)
                .filter(
                    GithubRepo.id == repo_id,
                    GithubRepo.status.in_(["pending", "failed"]),
                )
                .update({"status": "indexing", "error_message": ""}, synchronize_session=False)
            )
            db.commit()
            if not claimed:
                return

            record = self.get_repo(db, repo_id)
            if not record:
                return

            try:
                self._clone(record, token)
            except Exception as e:
                record.status = "failed"
                record.error_message = f"Clone failed: {_redact_secrets(str(e)[:400], token)}"
                db.commit()
                return

            code_files = self._collect_code_files(record.clone_path)
            graph = build_repo_graph(record.clone_path)

            try:
                self.vectorstore._collection.delete(where={"repo_id": repo_id})
            except Exception:
                pass

            lc_docs: List[Document] = []
            for rel_path, content in code_files:
                if not content.strip():
                    continue
                chunks = self.splitter.split_text(content)
                for idx, chunk in enumerate(chunks):
                    lc_docs.append(
                        Document(
                            page_content=chunk,
                            metadata={
                                "repo_id": repo_id,
                                "file_path": rel_path,
                                "owner": record.owner,
                                "repo_name": record.name,
                                "chunk_index": idx,
                            },
                        )
                    )

            for i in range(0, len(lc_docs), EMBED_BATCH):
                batch = lc_docs[i : i + EMBED_BATCH]
                self.vectorstore.add_documents(batch)

            record.status = "ready"
            record.file_count = len(code_files)
            record.chunk_count = len(lc_docs)
            record.graph_json = json.dumps(graph)
            record.indexed_at = datetime.utcnow()
            record.error_message = ""
            db.commit()
        except Exception as e:
            record = self.get_repo(db, repo_id)
            if record:
                record.status = "failed"
                record.error_message = str(e)[:500]
                db.commit()
        finally:
            db.close()

    def delete_repo(
        self, db: Session, repo_id: str, user_id: Optional[str] = None
    ) -> bool:
        record = self.get_repo(db, repo_id, user_id=user_id)
        if not record:
            return False

        try:
            self.vectorstore._collection.delete(where={"repo_id": repo_id})
        except Exception:
            pass

        if record.clone_path and os.path.exists(record.clone_path):
            shutil.rmtree(record.clone_path, ignore_errors=True)

        db.delete(record)
        db.commit()
        return True

    def get_graph(self, db: Session, repo_id: str) -> dict:
        record = self.get_repo(db, repo_id)
        if not record:
            return {"nodes": [], "edges": []}
        try:
            return json.loads(record.graph_json or "{}")
        except json.JSONDecodeError:
            return {"nodes": [], "edges": []}

    def _search_chunks(
        self, repo_ids: List[str], query: str, k: Optional[int] = None
    ) -> Tuple[List[dict], float]:
        if not repo_ids:
            return [], 0.0

        k = k or settings.github_retrieval_k
        where_filter = {"repo_id": {"$in": repo_ids}}

        try:
            results = self.vectorstore.similarity_search_with_score(
                query, k=k, filter=where_filter
            )
        except Exception:
            results = []

        if not results:
            return [], 0.0

        best_score = 1.0 - results[0][1] if results else 0.0
        hits = []
        for doc, distance in results:
            similarity = max(0.0, 1.0 - distance)
            hits.append({
                "content": doc.page_content,
                "file_path": doc.metadata.get("file_path", ""),
                "repo_name": doc.metadata.get("repo_name", ""),
                "owner": doc.metadata.get("owner", ""),
                "chunk_index": doc.metadata.get("chunk_index", 0),
                "similarity": round(similarity, 3),
            })
        return hits, best_score

    def search(
        self, db: Session, repo_ids: List[str], query: str, k: Optional[int] = None
    ) -> List[dict]:
        ready_ids = [
            r.id for r in self.list_repos(db)
            if r.id in repo_ids and r.status == "ready"
        ]
        hits, _ = self._search_chunks(ready_ids, query, k)
        return hits

    def is_build_request(self, message: str) -> bool:
        return detect_build_request(message)

    def get_relevant_context(
        self,
        db: Session,
        repo_ids: List[str],
        query: str,
        force: bool = False,
    ) -> Tuple[List[dict], bool, List[str]]:
        """Returns (hits, is_relevant, repo_names_used)."""
        ready = [
            r for r in self.list_repos(db)
            if r.id in repo_ids and r.status == "ready"
        ]
        if not ready:
            return [], False, []

        ready_ids = [r.id for r in ready]
        hits, best_score = self._search_chunks(ready_ids, query)

        is_build = self.is_build_request(query)
        threshold = settings.github_relevance_threshold
        if is_build:
            threshold = min(threshold, 0.35)

        is_relevant = force or (bool(hits) and best_score >= threshold)
        if not is_relevant:
            return hits[:3], False, []

        repo_names = list({f"{h['owner']}/{h['repo_name']}" for h in hits if h.get("repo_name")})
        return hits, True, repo_names

    async def query_repo(self, db: Session, repo_id: str, question: str) -> dict:
        record = self.get_repo(db, repo_id)
        if not record:
            return {"answer": "Repository not found.", "sources": [], "relevant": False}
        if record.status != "ready":
            return {
                "answer": f"Repository is not ready (status: {record.status}).",
                "sources": [],
                "relevant": False,
            }

        hits, score = self._search_chunks([repo_id], question, k=settings.github_retrieval_k)
        if not hits:
            return {
                "answer": "No indexed code found for this repository.",
                "sources": [],
                "relevant": False,
            }

        blocks = []
        for h in hits:
            blocks.append(
                f"[{h['file_path']} chunk {h['chunk_index']}]\n{h['content']}"
            )
        context = "\n\n---\n\n".join(blocks)

        llm = get_llm(streaming=False)
        prompt = (
            f"You are analyzing the GitHub repository {record.owner}/{record.name}.\n"
            f"Answer the user's question using ONLY the code excerpts below.\n"
            f"Cite file paths when relevant. If the answer is not in the excerpts, say so.\n\n"
            f"Code excerpts:\n{context}\n\n"
            f"Question: {question}"
        )
        response = await llm.ainvoke(prompt)
        answer = response.content if hasattr(response, "content") else str(response)

        sources = [
            {"file_path": h["file_path"], "chunk_index": h["chunk_index"], "similarity": h["similarity"]}
            for h in hits[:6]
        ]
        return {
            "answer": answer,
            "sources": sources,
            "relevant": score >= settings.github_relevance_threshold,
            "repo": f"{record.owner}/{record.name}",
        }


github_repo_service = GithubRepoService()
