from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import os

from app.models.database import User, get_db
from app.models.schemas import DocumentResponse
from app.services.document_service import document_service
from app.services import user_auth as auth
from app.services.ownership import owned_session_or_404

router = APIRouter(
    prefix="/api/documents",
    tags=["documents"],
    dependencies=[Depends(auth.get_current_user)],
)


@router.get("/{session_id}", response_model=List[DocumentResponse])
def list_documents(
    session_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(auth.get_current_user),
):
    owned_session_or_404(db, session_id, user)
    docs = document_service.list_documents(db, session_id)
    return docs


@router.post("/upload", response_model=List[DocumentResponse])
async def upload_documents(
    background_tasks: BackgroundTasks,
    session_id: str = Form(...),
    ocr_model: str = Form(default="auto"),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(auth.get_current_user),
):
    owned_session_or_404(db, session_id, user)

    pdf_files = [f for f in files if f.filename and f.filename.lower().endswith(".pdf")]
    if not pdf_files:
        raise HTTPException(status_code=400, detail="No PDF files provided")

    records = await document_service.save_uploads(db, session_id, pdf_files)
    doc_ids = [r.id for r in records]
    background_tasks.add_task(document_service.process_pending_batch, doc_ids, ocr_model)
    return records


@router.get("/file/{doc_id}")
def get_document_file(
    doc_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(auth.get_current_user),
):
    doc = document_service.get_document(db, doc_id)
    if not doc or doc.status == "removed":
        raise HTTPException(status_code=404, detail="Document not found")
    owned_session_or_404(db, doc.session_id, user)
    path = document_service.document_file_path(doc.session_id, doc.id)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found on disk")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=doc.filename,
        headers={"Content-Disposition": f'inline; filename="{doc.filename}"'},
    )


@router.delete("/{doc_id}")
def delete_document(
    doc_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(auth.get_current_user),
):
    doc = document_service.get_document(db, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    owned_session_or_404(db, doc.session_id, user)
    if not document_service.delete_document(db, doc_id):
        raise HTTPException(status_code=404, detail="Document not found")
    return {"ok": True}
