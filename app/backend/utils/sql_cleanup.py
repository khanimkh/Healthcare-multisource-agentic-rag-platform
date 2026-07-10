import re


def clean_sql_response(response: str) -> str:
    text = response.strip()
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    text = re.sub(r"^sql\s*\n", "", text, flags=re.IGNORECASE)
    return text.strip()
