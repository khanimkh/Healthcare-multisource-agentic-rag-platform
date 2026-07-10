import pandas as pd
from sqlalchemy import create_engine

from app.backend.config.settings import settings
from app.backend.utils.naming import normalize_table_name


class RelationalDataStore:
    def __init__(self):
        self.engine = create_engine(settings.postgres_url)

    def load_dataframe(self, dataset_name: str, df: pd.DataFrame) -> str:
        table_name = normalize_table_name(dataset_name)
        df.to_sql(table_name, self.engine, if_exists="replace", index=False)
        return table_name
