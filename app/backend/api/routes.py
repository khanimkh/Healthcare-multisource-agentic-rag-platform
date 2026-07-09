import os
import shutil
import uuid
from typing import List

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.backend.schemas.document_schema import DocumentRecordResponse
from app.backend.schemas.question_schema import QuestionRequest, QuestionResponse
from app.backend.schemas.upload_schema import UploadResponse
from app.backend.services.document_store_service import DocumentStore
from app.backend.tools.data_loader import detect_file_type
from app.backend.workflows.document_ingestion_workflow import DocumentIngestionWorkflow
from app.backend.workflows.question_workflow import QuestionWorkflow
from app.backend.workflows.structured_ingestion_workflow import StructuredIngestionWorkflow
from app.backend.utils.logger import get_logger


logger = get_logger(__name__)

router = APIRouter()

document_ingestion_workflow = DocumentIngestionWorkflow()
structured_ingestion_workflow = StructuredIngestionWorkflow()
question_workflow = QuestionWorkflow()
document_store = DocumentStore()


UPLOAD_DIR = "app/backend/data/raw"


@router.post("/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)):
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    original_file_name = file.filename
    local_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}_{original_file_name}")

    with open(local_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    file_type = detect_file_type(local_path)

    if file_type == "unknown":
        os.remove(local_path)
        logger.warning(f"Rejected upload with unsupported file type: {original_file_name!r}")
        raise HTTPException(status_code=400, detail="Unsupported file type.")

    logger.info(f"Upload received: {original_file_name!r} (type={file_type}).")

    try:
        if file_type == "structured":
            result = structured_ingestion_workflow.ingest(
                file_path=local_path,
                file_name=original_file_name
            )
        else:
            result = document_ingestion_workflow.ingest(
                file_path=local_path,
                file_name=original_file_name
            )

        return UploadResponse(file_type=file_type, **result)

    except Exception as e:
        logger.error(f"Upload failed for {original_file_name!r}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if os.path.exists(local_path):
            os.remove(local_path)


@router.get("/documents", response_model=List[DocumentRecordResponse])
async def list_documents():
    try:
        return document_store.list_all_documents()

    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/documents/{file_id}")
async def delete_document(file_id: str):
    document = document_store.get_document(file_id)

    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    try:
        document_ingestion_workflow.vector_store.delete_chunks(file_id)
        document_ingestion_workflow.storage.delete_file(document["s3_uri"])
        document_store.delete_document(file_id)

        logger.info(f"Deleted document {document['file_name']!r} (file_id={file_id}).")

        return {
            "status": "deleted",
            "file_id": file_id,
            "note": (
                "Removed from S3, the document list, and the vector index. "
                "Any Glue table or knowledge-graph entries created from this document "
                "are not automatically cleaned up."
            )
        }

    except Exception as e:
        logger.error(f"Failed to delete document {file_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ask", response_model=QuestionResponse)
async def ask_question(request: QuestionRequest):
    try:
        result = question_workflow.ask(
            question=request.question,
            session_id=request.session_id
        )

        return QuestionResponse(**result)

    except Exception as e:
        logger.error(f"Ask failed for question={request.question!r}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
