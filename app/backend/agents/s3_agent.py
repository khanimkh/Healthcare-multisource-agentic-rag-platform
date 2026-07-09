from typing import Any, Dict

from app.backend.prompts.sql_prompt import SQL_SYSTEM_PROMPT, build_sql_prompt
from app.backend.services.athena_service import AthenaService
from app.backend.services.llm_service import LLMService
from app.backend.utils.logger import get_logger
from app.backend.utils.validators import is_read_only_sql


logger = get_logger(__name__)


class S3Agent:
    def __init__(self):
        self.llm_service = LLMService()
        self.athena_service = AthenaService()

    def describe_schema(self) -> str:
        tables = self.athena_service.list_tables()
        return "\n".join(f"- {table}" for table in tables) or "no tables registered"

    def generate_sql(self, question: str) -> str:
        schema_description = self.describe_schema()

        prompt = build_sql_prompt(
            question=question,
            schema_description=schema_description,
            dialect="Amazon Athena (Presto) SQL"
        )

        sql = self.llm_service.generate(
            prompt=prompt,
            system_prompt=SQL_SYSTEM_PROMPT,
            max_tokens=300,
            temperature=0
        )

        return sql.strip().strip("`").strip()

    def answer(self, question: str) -> Dict[str, Any]:
        sql = self.generate_sql(question)

        if not is_read_only_sql(sql):
            logger.warning(f"Rejected unsafe Athena SQL: {sql!r}")
            raise ValueError("Only read-only SELECT queries are allowed.")

        rows = self.athena_service.run_query(sql)
        logger.info(f"Athena query executed, {len(rows)} row(s) returned. sql={sql!r}")

        return {
            "sql": sql,
            "rows": rows
        }
