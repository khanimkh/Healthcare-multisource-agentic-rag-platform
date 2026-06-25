import os
import uuid
import shutil
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.backend.schemas.upload_schema import UploadResponse
from app.backend.tools.data_loader import (
    detect_file_type,
    load_data,
    clean_dataframe,
    clean_text
)
from app.backend.tools.aws_storage import AWSStorage, OpenSearchVectorStore
from app.backend.tools.database import RDSStorage
from app.backend.tools.rag_utils import chunk_documents, create_embeddings_for_chunks
from app.backend.tools.glue_catalog import GlueCatalog
from app.backend.agents.classification_agent import ClassificationAgent
from app.backend.services.cache_service import CacheService
from app.backend.config.settings import settings


router = APIRouter()


UPLOAD_DIR = "app/backend/data/raw"


@router.post("/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)):
    try:
        os.makedirs(UPLOAD_DIR, exist_ok=True)

        file_id = str(uuid.uuid4())
        original_file_name = file.filename
        local_path = os.path.join(UPLOAD_DIR, f"{file_id}_{original_file_name}")

        with open(local_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        file_type = detect_file_type(local_path)

        if file_type == "unknown":
            raise HTTPException(status_code=400, detail="Unsupported file type.")

        aws_storage = AWSStorage()
        glue_catalog = GlueCatalog()
        classifier = ClassificationAgent()
        cache = CacheService()

        s3_key = f"raw/{file_id}/{original_file_name}"
        s3_uri = aws_storage.upload_file_to_s3(local_path, s3_key)

        loaded_data = load_data(local_path)

        response_metadata = {
            "file_id": file_id,
            "original_file_name": original_file_name
        }

        document_type = None
        rds_table = None
        chunks_created = 0
        opensearch_index = None

        if file_type == "structured":
            df = clean_dataframe(loaded_data)
            document_type = classifier.classify_structured_data(df)

            table_name = f"dataset_{file_id.replace('-', '_')}"
            rds = RDSStorage()
            rds_table = rds.save_dataframe(df, table_name)

            response_metadata["columns"] = df.columns.tolist()
            response_metadata["rows"] = len(df)

        elif file_type in ["document", "image"]:
            text = clean_text(loaded_data)
            document_type = classifier.classify_document(text)

            chunks = chunk_documents(text)
            embedded_chunks = create_embeddings_for_chunks(chunks)

            vector_store = OpenSearchVectorStore()
            vector_store.index_chunks(
                chunks=embedded_chunks,
                file_name=original_file_name,
                document_type=document_type
            )

            chunks_created = len(chunks)
            opensearch_index = settings.opensearch_index

            response_metadata["text_length"] = len(text)

        glue_registered = glue_catalog.register_metadata(
            dataset_name=original_file_name,
            s3_uri=s3_uri,
            file_type=file_type,
            metadata={
                "document_type": document_type,
                "file_id": file_id,
                "rds_table": rds_table,
                "opensearch_index": opensearch_index,
                "chunks_created": chunks_created
            }
        )

        cache_key = f"upload:{file_id}"
        cache.set_json(
            cache_key,
            {
                "file_name": original_file_name,
                "file_type": file_type,
                "document_type": document_type,
                "s3_uri": s3_uri,
                "rds_table": rds_table,
                "opensearch_index": opensearch_index
            }
        )

        return UploadResponse(
            status="success",
            file_name=original_file_name,
            file_type=file_type,
            document_type=document_type,
            s3_uri=s3_uri,
            rds_table=rds_table,
            opensearch_index=opensearch_index,
            glue_registered=glue_registered,
            chunks_created=chunks_created,
            cached=True,
            metadata=response_metadata
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))