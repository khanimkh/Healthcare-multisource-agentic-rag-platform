CHART_SUGGESTION_SYSTEM_PROMPT = (
    "You propose short, meaningful charting questions a user could ask about the "
    "data described by a database schema (for example: 'Number of patients by "
    "diagnosis'). Favor questions answerable with GROUP BY plus COUNT, SUM, or AVG "
    "over categorical columns. Return ONLY a JSON array of question strings, "
    "nothing else."
)


def build_chart_suggestion_prompt(schema_description: str, limit: int = 6) -> str:
    return f"""
    Schema:
    {schema_description}

    Propose up to {limit} short, meaningful charting questions about this data.
    Return a JSON array of strings only.
    """


CHART_SQL_SYSTEM_PROMPT = (
    "You write a single read-only PostgreSQL SELECT statement that answers a "
    "charting question over the given schema. The query MUST return exactly two "
    "columns aliased 'label' and 'value' (for example: SELECT diagnosis AS label, "
    "COUNT(*) AS value FROM patients GROUP BY diagnosis). Use GROUP BY with COUNT, "
    "SUM, or AVG as appropriate, ORDER BY value DESC, and LIMIT 20. Each table's "
    "example row shows the actual value types/formats stored in each column (e.g. "
    "yes/no text instead of boolean) — match those exact types and formats in any "
    "comparisons instead of guessing. Return ONLY the SQL statement, no "
    "explanation, no markdown."
)


def build_chart_sql_prompt(question: str, schema_description: str) -> str:
    return f"""
    Schema:
    {schema_description}

    Charting question:
    {question}

    Write one PostgreSQL SELECT statement returning columns aliased label and value.
    """
