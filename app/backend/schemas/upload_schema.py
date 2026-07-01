from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class UploadResponse(BaseModel):
    status: str
    file_name: str
    file_type: str
    document_type: Optional[str] = None
    s3_uri: Optional[str] = None
    rds_table: Optional[str] = None
    opensearch_index: Optional[str] = None
    glue_registered: bool = False
    chunks_created: int = 0
    cached: bool = False
    metadata: Dict[str, Any] = {}