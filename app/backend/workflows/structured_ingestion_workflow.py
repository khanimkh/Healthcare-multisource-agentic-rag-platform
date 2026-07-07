from pathlib import Path
from typing import Dict, Any

import pandas as pd

from app.backend.services.aws_storage_service import AWSStorage
from app.backend.services.document_store_service import DocumentStore
from app.backend.services.glue_catalog_service import GlueCatalog
from app.backend.config.settings import settings


class StructuredIngestionWorkflow:
    def __init__(self):
        self.storage = AWSStorage()
        self.document_store = DocumentStore()
        self.glue_catalog = GlueCatalog()

    def ingest_csv(
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
            document_type="structured_dataset"
        )

        try:
            self.document_store.update_status(
                file_id=file_id,
                status="processing"
            )

            df = pd.read_csv(file_path)

            dataset_name = Path(file_name).stem

            table_name = self.glue_catalog.register_csv_table(
                dataset_name=dataset_name,
                s3_uri=s3_uri,
                df=df
            )

            self.document_store.update_status(
                file_id=file_id,
                status="registered",
                document_type="structured_dataset"
            )

            return {
                "status": "registered",
                "file_id": file_id,
                "file_name": file_name,
                "s3_uri": s3_uri,
                "glue_database": settings.glue_database_name,
                "glue_table": table_name,
                "rows": len(df),
                "columns": list(df.columns)
            }

        except Exception as error:
            self.document_store.update_status(
                file_id=file_id,
                status="failed",
                error_message=str(error)
            )
            raise

    def ingest(
        self,
        file_path: str,
        file_name: str
    ) -> Dict[str, Any]:

        extension = Path(file_name).suffix.lower()

        if extension == ".csv":
            return self.ingest_csv(file_path, file_name)

        raise ValueError(f"Unsupported structured file type: {extension}")