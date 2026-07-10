from typing import Any, Dict, List

from app.backend.agents.chart_agent import ChartAgent
from app.backend.services.schema_service import SchemaService
from app.backend.utils.logger import get_logger


logger = get_logger(__name__)


class VisualizationWorkflow:
    def __init__(self):
        self.schema_service = SchemaService()
        self.chart_agent = ChartAgent()

    def _schema_description(self) -> str:
        schema = self.schema_service.describe_tables()
        return self.schema_service.format_description(schema)

    def suggest(self) -> List[str]:
        return self.chart_agent.suggest_questions(self._schema_description())

    def chart(self, question: str) -> Dict[str, Any]:
        schema_description = self._schema_description()

        if schema_description == "no tables available":
            return {"title": question, "sql": None, "labels": [], "values": []}

        logger.info(f"Building chart for question={question!r}")

        return self.chart_agent.build_chart(question=question, schema_description=schema_description)
