import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection, helpers
from requests_aws4auth import AWS4Auth

from app.backend.config.settings import settings


class AWSStorage:

    def __init__(self):
        self.s3 = boto3.client("s3", region_name=settings.aws_region)

    def upload_file_to_s3(self, file_path: str, file_name: str) -> Dict[str, str]:
        file_id = str(uuid.uuid4())
        s3_key = f"uploads/{file_id}/{file_name}"

        self.s3.upload_file(
            file_path,
            settings.s3_bucket_name,
            s3_key
        )

        s3_uri = f"s3://{settings.s3_bucket_name}/{s3_key}"

        return {
            "file_id": file_id,
            "file_name": file_name,
            "s3_key": s3_key,
            "s3_uri": s3_uri
        }


class OpenSearchVectorStore:

    def __init__(self):
        session = boto3.Session()
        credentials = session.get_credentials()

        auth = AWS4Auth(
            credentials.access_key,
            credentials.secret_key,
            settings.aws_region,
            "es",
            session_token=credentials.token
        )

        self.client = OpenSearch(
            hosts=[{"host": settings.opensearch_host, "port": 443}],
            http_auth=auth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection
        )

    def create_index_if_not_exists(self, dimension: int):
        if self.client.indices.exists(index=settings.opensearch_index):
            return

        index_body = {
            "settings": {
                "index": {
                    "knn": True
                }
            },
            "mappings": {
                "properties": {
                    "text": {"type": "text"},
                    "file_id": {"type": "keyword"},
                    "chunk_id": {"type": "keyword"},
                    "chunk_index": {"type": "integer"},
                    "file_name": {"type": "keyword"},
                    "document_type": {"type": "keyword"},
                    "s3_uri": {"type": "keyword"},
                    "uploaded_at": {"type": "date"},
                    "metadata": {"type": "object", "enabled": True},
                    "embedding": {
                        "type": "knn_vector",
                        "dimension": dimension
                    }
                }
            }
        }

        self.client.indices.create(
            index=settings.opensearch_index,
            body=index_body
        )

    def index_chunks(
        self,
        chunks: List[Dict[str, Any]],
        file_id: str,
        file_name: str,
        document_type: str,
        s3_uri: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        batch_size: int = 500
    ) -> None:
        if not chunks:
            return

        uploaded_at = datetime.now(timezone.utc).isoformat()
        metadata = metadata or {}

        dimension = len(chunks[0]["embedding"])
        self.create_index_if_not_exists(dimension=dimension)

        actions = []

        for chunk_index, chunk in enumerate(chunks):
            chunk_id = f"{file_id}_{chunk_index}"

            document = {
                "text": chunk["text"],
                "file_id": file_id,
                "chunk_id": chunk_id,
                "chunk_index": chunk_index,
                "file_name": file_name,
                "document_type": document_type,
                "s3_uri": s3_uri,
                "uploaded_at": uploaded_at,
                "metadata": metadata,
                "embedding": chunk["embedding"]
            }

            actions.append({
                "_op_type": "index",
                "_index": settings.opensearch_index,
                "_id": chunk_id,
                "_source": document
            })

        helpers.bulk(
            self.client,
            actions,
            chunk_size=batch_size
        )