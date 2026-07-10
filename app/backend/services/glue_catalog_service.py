from typing import Dict

import boto3
import pandas as pd

from app.backend.config.settings import settings
from app.backend.utils.naming import normalize_table_name


class GlueCatalog:
    def __init__(self):
        self.client = boto3.client("glue", region_name=settings.aws_region)

    def _map_dtype_to_glue(self, dtype) -> str:
        dtype = str(dtype)

        if "int" in dtype:
            return "bigint"
        if "float" in dtype:
            return "double"
        if "bool" in dtype:
            return "boolean"
        if "datetime" in dtype:
            return "timestamp"

        return "string"

    def ensure_database_exists(self) -> None:
        try:
            self.client.get_database(
                Name=settings.glue_database_name
            )
        except self.client.exceptions.EntityNotFoundException:
            self.client.create_database(
                DatabaseInput={
                    "Name": settings.glue_database_name,
                    "Description": "Healthcare RAG structured data catalog"
                }
            )

    def register_csv_table(
        self,
        dataset_name: str,
        s3_uri: str,
        df: pd.DataFrame
    ) -> str:
        self.ensure_database_exists()

        table_name = normalize_table_name(dataset_name)

        columns = [
            {
                "Name": normalize_table_name(column),
                "Type": self._map_dtype_to_glue(dtype)
            }
            for column, dtype in df.dtypes.items()
        ]

        table_input = {
            "Name": table_name,
            "TableType": "EXTERNAL_TABLE",
            "Parameters": {
                "classification": "csv",
                "skip.header.line.count": "1"
            },
            "StorageDescriptor": {
                "Columns": columns,
                "Location": s3_uri,
                "InputFormat": "org.apache.hadoop.mapred.TextInputFormat",
                "OutputFormat": "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat",
                "SerdeInfo": {
                    "SerializationLibrary": "org.apache.hadoop.hive.serde2.OpenCSVSerde",
                    "Parameters": {
                        "separatorChar": ",",
                        "quoteChar": "\""
                    }
                }
            }
        }

        try:
            self.client.get_table(
                DatabaseName=settings.glue_database_name,
                Name=table_name
            )

            self.client.update_table(
                DatabaseName=settings.glue_database_name,
                TableInput=table_input
            )

        except self.client.exceptions.EntityNotFoundException:
            self.client.create_table(
                DatabaseName=settings.glue_database_name,
                TableInput=table_input
            )

        return table_name