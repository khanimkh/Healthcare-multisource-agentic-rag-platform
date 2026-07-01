import os
import pandas as pd
from pypdf import PdfReader
from docx import Document
from PIL import Image
import pytesseract


STRUCTURED_EXTENSIONS = {".csv", ".xlsx", ".xls"}
DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".txt"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}


def detect_file_type(file_path: str) -> str:
    ext = os.path.splitext(file_path.lower())[1]

    if ext in STRUCTURED_EXTENSIONS:
        return "structured"

    if ext in DOCUMENT_EXTENSIONS:
        return "document"

    if ext in IMAGE_EXTENSIONS:
        return "image"

    return "unknown"


def load_csv(file_path: str) -> pd.DataFrame:
    return pd.read_csv(file_path)


def load_excel(file_path: str) -> pd.DataFrame:
    return pd.read_excel(file_path)


def load_pdf(file_path: str) -> str:
    reader = PdfReader(file_path)
    pages = []

    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)

    return "\n".join(pages)


def load_docx(file_path: str) -> str:
    document = Document(file_path)
    return "\n".join([p.text for p in document.paragraphs])


def load_txt(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def load_image_ocr(file_path: str) -> str:
    image = Image.open(file_path)
    return pytesseract.image_to_string(image)


def load_data(file_path: str):
    ext = os.path.splitext(file_path.lower())[1]

    if ext == ".csv":
        return load_csv(file_path)

    if ext in [".xlsx", ".xls"]:
        return load_excel(file_path)

    if ext == ".pdf":
        return load_pdf(file_path)

    if ext == ".docx":
        return load_docx(file_path)

    if ext == ".txt":
        return load_txt(file_path)

    if ext in IMAGE_EXTENSIONS:
        return load_image_ocr(file_path)

    raise ValueError(f"Unsupported file type: {ext}")


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [
        col.strip().lower().replace(" ", "_")
        for col in df.columns
    ]
    df = df.drop_duplicates()
    return df


def clean_text(text: str) -> str:
    return " ".join(text.split())