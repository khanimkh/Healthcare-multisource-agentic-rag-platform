from typing import List, Optional

from pydantic import BaseModel


class UploadResponse(BaseModel):
    status: str
    file_type: str
    file_id: str
    file_name: str
    s3_uri: str

    document_type: Optional[str] = None
    chunks_indexed: Optional[int] = None
    entities_extracted: Optional[int] = None
    relationships_extracted: Optional[int] = None

    glue_database: Optional[str] = None
    glue_table: Optional[str] = None
    rows: Optional[int] = None
    columns: Optional[List[str]] = None
