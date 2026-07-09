# NOTE: importing app.backend.tools.data_loader pulls in pypdf/python-docx/Pillow/
# pytesseract at module level, even though detect_file_type() itself never touches
# them. So this test file needs `pip install -r requirements.txt` to even import,
# despite detect_file_type() being pure, dependency-free logic.

from app.backend.tools.data_loader import detect_file_type


def test_detects_csv_as_structured():
    assert detect_file_type("patients.csv") == "structured"


def test_detects_xlsx_as_structured():
    assert detect_file_type("visits.xlsx") == "structured"


def test_detects_pdf_as_document():
    assert detect_file_type("guideline.pdf") == "document"


def test_detects_docx_as_document():
    assert detect_file_type("policy.docx") == "document"


def test_detects_txt_as_document():
    assert detect_file_type("notes.txt") == "document"


def test_detects_png_as_image():
    assert detect_file_type("scan.png") == "image"


def test_detects_unknown_extension():
    assert detect_file_type("archive.zip") == "unknown"


def test_detection_is_case_insensitive():
    assert detect_file_type("PATIENTS.CSV") == "structured"
