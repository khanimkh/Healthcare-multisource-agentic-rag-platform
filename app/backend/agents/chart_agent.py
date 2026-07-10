import json
import re
from typing import Any, Dict, List

from app.backend.agents.sql_agent import SQLAgent
from app.backend.prompts.chart_prompt import (
    CHART_SQL_SYSTEM_PROMPT,
    CHART_SUGGESTION_SYSTEM_PROMPT,
    build_chart_sql_prompt,
    build_chart_suggestion_prompt,
)
from app.backend.services.llm_service import LLMService
from app.backend.utils.logger import get_logger
from app.backend.utils.sql_cleanup import clean_sql_response


logger = get_logger(__name__)


class ChartAgent:
    def __init__(self):
        self.llm_service = LLMService()
        self.sql_agent = SQLAgent()

    def suggest_questions(self, schema_description: str, limit: int = 6) -> List[str]:
        if schema_description == "no tables available":
            return []

        prompt = build_chart_suggestion_prompt(schema_description, limit=limit)

        response = self.llm_service.generate(
            prompt=prompt,
            system_prompt=CHART_SUGGESTION_SYSTEM_PROMPT,
            max_tokens=400,
            temperature=0.3
        )

        questions = self._parse_question_list(response)

        if questions is None:
            logger.warning("Chart suggestion response could not be parsed.")
            return []

        return questions

    def _parse_question_list(self, response: str) -> List[str]:
        match = re.search(r"\[[\s\S]*\]", response)

        if not match:
            return None

        try:
            questions = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

        if not isinstance(questions, list):
            return None

        return [q for q in questions if isinstance(q, str) and q.strip()]

    def build_chart(self, question: str, schema_description: str) -> Dict[str, Any]:
        prompt = build_chart_sql_prompt(question=question, schema_description=schema_description)

        sql = clean_sql_response(self.llm_service.generate(
            prompt=prompt,
            system_prompt=CHART_SQL_SYSTEM_PROMPT,
            max_tokens=300,
            temperature=0
        ))

        rows = self.sql_agent.execute(sql)

        if not rows:
            return {"title": question, "sql": sql, "labels": [], "values": []}

        keys = list(rows[0].keys())
        label_key, value_key = ("label", "value") if "label" in keys and "value" in keys else (
            keys[0], keys[1] if len(keys) > 1 else keys[0]
        )

        labels = [str(row[label_key]) for row in rows]
        values = [round(float(row[value_key]), 2) if row[value_key] is not None else 0 for row in rows]

        return {"title": question, "sql": sql, "labels": labels, "values": values}
