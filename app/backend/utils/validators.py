import re
from typing import List


BLOCKED_SQL_KEYWORDS: List[str] = [
    "drop", "delete", "update", "insert", "alter", "truncate", "grant", "revoke"
]


def is_read_only_sql(sql: str) -> bool:
    lowered = sql.strip().lower()

    if not lowered.startswith("select"):
        return False

    return not any(
        re.search(rf"\b{keyword}\b", lowered) for keyword in BLOCKED_SQL_KEYWORDS
    )
