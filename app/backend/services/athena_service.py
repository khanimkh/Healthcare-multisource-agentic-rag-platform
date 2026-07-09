import time
from typing import Any, Dict, List

import boto3

from app.backend.config.settings import settings
from app.backend.services.glue_catalog_service import GlueCatalog


class AthenaService:
    def __init__(self):
        self.client = boto3.client("athena", region_name=settings.aws_region)
        self.glue_catalog = GlueCatalog()

    def list_tables(self) -> List[str]:
        self.glue_catalog.ensure_database_exists()

        paginator = self.glue_catalog.client.get_paginator("get_tables")

        tables = []
        for page in paginator.paginate(DatabaseName=settings.glue_database_name):
            tables.extend(table["Name"] for table in page["TableList"])

        return tables

    def run_query(
        self,
        sql: str,
        poll_interval: float = 1.0,
        timeout: float = 60.0
    ) -> List[Dict[str, Any]]:
        query_execution = self.client.start_query_execution(
            QueryString=sql,
            QueryExecutionContext={"Database": settings.glue_database_name},
            ResultConfiguration={"OutputLocation": settings.athena_output_s3_uri}
        )

        query_execution_id = query_execution["QueryExecutionId"]
        elapsed = 0.0

        while elapsed < timeout:
            status = self.client.get_query_execution(QueryExecutionId=query_execution_id)
            state = status["QueryExecution"]["Status"]["State"]

            if state == "SUCCEEDED":
                break

            if state in ["FAILED", "CANCELLED"]:
                reason = status["QueryExecution"]["Status"].get("StateChangeReason", "Unknown error")
                raise RuntimeError(f"Athena query {state.lower()}: {reason}")

            time.sleep(poll_interval)
            elapsed += poll_interval
        else:
            raise TimeoutError("Athena query timed out.")

        results = self.client.get_query_results(QueryExecutionId=query_execution_id)
        rows = results["ResultSet"]["Rows"]

        if not rows:
            return []

        columns = [cell["VarCharValue"] for cell in rows[0]["Data"]]
        records = []

        for row in rows[1:]:
            values = [cell.get("VarCharValue") for cell in row["Data"]]
            records.append(dict(zip(columns, values)))

        return records
