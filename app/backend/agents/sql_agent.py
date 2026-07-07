from typing import Any, Dict, List

from sqlalchemy import create_engine, text

from app.backend.config.settings import settings
from app.backend.prompts.sql_prompt import SQL_SYSTEM_PROMPT, build_sql_prompt
from app.backend.services.llm_service import LLMService
from app.backend.utils.validators import is_read_only_sql


class SQLAgent:
    def __init__(self):
        self.llm_service = LLMService()
        self.engine = create_engine(settings.postgres_url)

    def generate_sql(self, question: str, schema_description: str) -> str:
        prompt = build_sql_prompt(
            question=question,
            schema_description=schema_description,
            dialect="PostgreSQL"
        )

        sql = self.llm_service.generate(
            prompt=prompt,
            system_prompt=SQL_SYSTEM_PROMPT,
            max_tokens=300,
            temperature=0
        )

        return sql.strip().strip("`").strip()

    def execute(self, sql: str) -> List[Dict[str, Any]]:
        if not is_read_only_sql(sql):
            raise ValueError("Only read-only SELECT queries are allowed.")

        with self.engine.connect() as connection:
            result = connection.execute(text(sql))
            columns = result.keys()
            return [dict(zip(columns, row)) for row in result.fetchall()]

    def answer(self, question: str, schema_description: str) -> Dict[str, Any]:
        sql = self.generate_sql(question, schema_description)
        rows = self.execute(sql)

        return {
            "sql": sql,
            "rows": rows
        }
