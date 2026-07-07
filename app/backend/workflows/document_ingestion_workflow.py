from pathlib import Path
from typing import Dict, Any

from app.backend.services.aws_storage_service import AWSStorage, OpenSearchVectorStore
from app.backend.services.bedrock_service import BedrockService
from app.backend.services.document_store_service import DocumentStore

from app.backend.tools.data_loader import load_document
from app.backend.tools.rag_utils import chunk_documents, create_embeddings_for_chunks


class DocumentIngestionWorkflow:
    def __init__(self):
        self.storage = AWSStorage()
        self.vector_store = OpenSearchVectorStore()
        self.bedrock = BedrockService()
        self.document_store = DocumentStore()

    def ingest(
        self,
        file_path: str,
        file_name: str
    ) -> Dict[str, Any]:

        upload_result = self.storage.upload_file_to_s3(
            file_path=file_path,
            file_name=file_name
        )

        file_id = upload_result["file_id"]
        s3_uri = upload_result["s3_uri"]

        self.document_store.create_document(
            file_id=file_id,
            file_name=file_name,
            s3_uri=s3_uri,
            document_type="document"
        )

        try:
            self.document_store.update_status(
                file_id=file_id,
                status="processing"
            )

            text = load_document(file_path)

            if not text or not text.strip():
                raise ValueError("No text could be extracted from the document.")

            document_type = self.bedrock.classify_text(text)

            text_chunks = chunk_documents(text)

            embedded_chunks = create_embeddings_for_chunks(text_chunks)

            self.vector_store.index_chunks(
                chunks=embedded_chunks,
                file_id=file_id,
                file_name=file_name,
                document_type=document_type,
                s3_uri=s3_uri,
                metadata={
                    "source": "user_upload",
                    "file_extension": Path(file_name).suffix.lower()
                },
                batch_size=500
            )

            self.document_store.update_status(
                file_id=file_id,
                status="indexed",
                document_type=document_type
            )

            return {
                "status": "indexed",
                "file_id": file_id,
                "file_name": file_name,
                "s3_uri": s3_uri,
                "document_type": document_type,
                "chunks_indexed": len(embedded_chunks)
            }

        except Exception as error:
            self.document_store.update_status(
                file_id=file_id,
                status="failed",
                error_message=str(error)
            )
            raise