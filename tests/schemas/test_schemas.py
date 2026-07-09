import pytest
from pydantic import ValidationError

from app.backend.schemas.question_schema import QuestionRequest, QuestionResponse
from app.backend.schemas.upload_schema import UploadResponse


def test_question_request_requires_question():
    with pytest.raises(ValidationError):
        QuestionRequest()


def test_question_request_session_id_defaults_to_none():
    request = QuestionRequest(question="hello")
    assert request.session_id is None


def test_question_response_defaults():
    response = QuestionResponse()
    assert response.answer is None
    assert response.sources == []


def test_upload_response_requires_core_fields():
    with pytest.raises(ValidationError):
        UploadResponse(status="success")


def test_upload_response_accepts_document_ingestion_shape():
    response = UploadResponse(
        status="indexed",
        file_type="document",
        file_id="abc123",
        file_name="guideline.txt",
        s3_uri="s3://bucket/key",
        document_type="clinical guideline",
        chunks_indexed=5,
        entities_extracted=10,
        relationships_extracted=4
    )
    assert response.glue_table is None
    assert response.chunks_indexed == 5


def test_upload_response_accepts_structured_ingestion_shape():
    response = UploadResponse(
        status="registered",
        file_type="structured",
        file_id="abc123",
        file_name="patients.csv",
        s3_uri="s3://bucket/key",
        glue_database="healthcare_rag_catalog",
        glue_table="patients",
        rows=20,
        columns=["patient_id", "age"]
    )
    assert response.chunks_indexed is None
    assert response.rows == 20
