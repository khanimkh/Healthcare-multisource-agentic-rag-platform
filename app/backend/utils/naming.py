import re


def normalize_table_name(name: str) -> str:
    name = name.lower()
    name = re.sub(r"[^a-z0-9_]", "_", name)
    return name.strip("_")
