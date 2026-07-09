from pathlib import Path
from typing import Dict, Any

from app.backend.agents.classification_agent import ClassificationAgent
from app.backend.services.aws_storage_service import AWSStorage, OpenSearchVectorStore
from app.backend.services.document_store_service import DocumentStore
from app.backend.services.graph_store_service import GraphStoreService

from app.backend.tools.data_loader import load_document
from app.backend.tools.entity_extraction import extract_entities_and_relationships
from app.backend.tools.rag_utils import chunk_documents, create_embeddings_for_chunks
from app.backend.utils.logger import get_logger


logger = get_logger(__name__)


class DocumentIngestionWorkflow:
    def __init__(self):
        self.storage = AWSStorage()
        self.vector_store = OpenSearchVectorStore()
        self.classification_agent = ClassificationAgent()
        self.document_store = DocumentStore()
        self.graph_store = GraphStoreService()

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

        logger.info(f"Starting document ingestion for {file_name!r} (file_id={file_id}).")

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

            document_type = self.classification_agent.classify_document(text)

            extraction = extract_entities_and_relationships(text)

            for relationship in extraction["relationships"]:
                self.graph_store.upsert_edge(
                    source_name=relationship["source"],
                    target_name=relationship["target"],
                    relationship=relationship["relationship"],
                    file_id=file_id,
                    evidence=relationship["evidence"]
                )

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

            logger.info(
                f"Document {file_name!r} indexed successfully. "
                f"chunks={len(embedded_chunks)}, entities={len(extraction['entities'])}, "
                f"relationships={len(extraction['relationships'])}."
            )

            return {
                "status": "indexed",
                "file_id": file_id,
                "file_name": file_name,
                "s3_uri": s3_uri,
                "document_type": document_type,
                "chunks_indexed": len(embedded_chunks),
                "entities_extracted": len(extraction["entities"]),
                "relationships_extracted": len(extraction["relationships"])
            }

        except Exception as error:
            logger.error(f"Document ingestion failed for {file_name!r} (file_id={file_id}): {error}")
            self.document_store.update_status(
                file_id=file_id,
                status="failed",
                error_message=str(error)
            )
            raise