SQL_SYSTEM_PROMPT = (
    "You are a healthcare SQL analyst. Generate a single read-only SQL SELECT "
    "query that answers the question using only the given schema. Return "
    "only the SQL query, with no explanation and no markdown formatting."
)


def build_sql_prompt(
    question: str,
    schema_description: str,
    dialect: str = "PostgreSQL"
) -> str:
    return f"""
    You are writing a {dialect} SELECT query.

    Database schema:
    {schema_description}

    Question:
    {question}

    Write one {dialect} SELECT query that answers the question.
    """
