import os
import shutil
import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.backend.schemas.question_schema import QuestionRequest, QuestionResponse
from app.backend.schemas.upload_schema import UploadResponse
from app.backend.tools.data_loader import detect_file_type
from app.backend.workflows.document_ingestion_workflow import DocumentIngestionWorkflow
from app.backend.workflows.question_workflow import QuestionWorkflow
from app.backend.workflows.structured_ingestion_workflow import StructuredIngestionWorkflow


router = APIRouter()


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
        raise HTTPException(status_code=400, detail="Unsupported file type.")

    try:
        if file_type == "structured":
            result = StructuredIngestionWorkflow().ingest(
                file_path=local_path,
                file_name=original_file_name
            )
        else:
            result = DocumentIngestionWorkflow().ingest(
                file_path=local_path,
                file_name=original_file_name
            )

        return UploadResponse(file_type=file_type, **result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if os.path.exists(local_path):
            os.remove(local_path)


@router.post("/ask", response_model=QuestionResponse)
async def ask_question(request: QuestionRequest):
    try:
        result = QuestionWorkflow().ask(
            question=request.question,
            session_id=request.session_id
        )

        return QuestionResponse(**result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
