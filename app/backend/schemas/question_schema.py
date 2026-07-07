from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class QuestionRequest(BaseModel):
    question: str
    session_id: Optional[str] = None


class QuestionResponse(BaseModel):
    answer: Optional[str] = None
    route: Optional[str] = None
    sql: Optional[str] = None
    sources: List[Dict[str, Any]] = []
