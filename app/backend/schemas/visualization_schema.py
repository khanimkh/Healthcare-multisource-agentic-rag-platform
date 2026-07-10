from typing import List, Optional

from pydantic import BaseModel


class ChartRequest(BaseModel):
    question: str


class ChartResponse(BaseModel):
    title: str
    sql: Optional[str] = None
    labels: List[str]
    values: List[float]


class ChartSuggestionsResponse(BaseModel):
    questions: List[str]
