from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine, inspect, text

from app.backend.config.settings import settings


INTERNAL_TABLES = {"documents", "conversation_messages", "graph_nodes", "graph_edges"}


class SchemaService:
    def __init__(self):
        self.engine = create_engine(settings.postgres_url)

    def describe_tables(self) -> Dict[str, List[str]]:
        inspector = inspect(self.engine)

        return {
            table_name: [column["name"] for column in inspector.get_columns(table_name)]
            for table_name in inspector.get_table_names()
            if table_name not in INTERNAL_TABLES
        }

    def sample_row(self, table_name: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as connection:
            result = connection.execute(text(f'SELECT * FROM "{table_name}" LIMIT 1'))
            row = result.fetchone()

            if row is None:
                return None

            return dict(zip(result.keys(), row))

    def format_description(self, schema: Dict[str, List[str]]) -> str:
        if not schema:
            return "no tables available"

        lines = []

        for table_name, columns in schema.items():
            lines.append(f"- {table_name}({', '.join(columns)})")

            sample = self.sample_row(table_name)
            if sample:
                lines.append(f"  example row (note actual value types/formats): {sample}")

        return "\n".join(lines)
