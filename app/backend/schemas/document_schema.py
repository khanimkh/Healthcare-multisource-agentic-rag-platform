from typing import Optional

from pydantic import BaseModel


class DocumentRecordResponse(BaseModel):
    file_id: str
    file_name: str
    document_type: Optional[str] = None
    status: str
    uploaded_at: Optional[str] = None
    processed_at: Optional[str] = None
    error_message: Optional[str] = None
