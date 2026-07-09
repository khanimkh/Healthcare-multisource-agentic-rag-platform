from app.backend.utils.validators import is_read_only_sql


def test_allows_simple_select():
    assert is_read_only_sql("SELECT * FROM patients") is True


def test_allows_select_case_insensitive():
    assert is_read_only_sql("select id from visits") is True


def test_allows_leading_whitespace():
    assert is_read_only_sql("   SELECT id FROM visits") is True


def test_rejects_non_select_statement():
    assert is_read_only_sql("UPDATE patients SET age = 30") is False


def test_rejects_drop_table():
    assert is_read_only_sql("SELECT * FROM patients; DROP TABLE patients;") is False


def test_rejects_delete():
    assert is_read_only_sql("DELETE FROM patients") is False


def test_rejects_insert():
    assert is_read_only_sql("INSERT INTO patients VALUES (1, 2, 3)") is False


def test_rejects_alter():
    assert is_read_only_sql("ALTER TABLE patients ADD COLUMN x INT") is False


def test_rejects_truncate():
    assert is_read_only_sql("TRUNCATE TABLE patients") is False


def test_rejects_grant_and_revoke():
    assert is_read_only_sql("GRANT ALL ON patients TO public") is False
    assert is_read_only_sql("REVOKE ALL ON patients FROM public") is False


def test_does_not_false_positive_on_column_named_like_a_keyword():
    # "dropout_rate" contains "drop" as a substring, not as a whole word
    assert is_read_only_sql("SELECT dropout_rate FROM patients") is True


def test_does_not_false_positive_on_updated_at_column():
    # "updated_at" contains "update" as a substring, not as a whole word
    assert is_read_only_sql("SELECT updated_at FROM patients") is True
