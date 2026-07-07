from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import create_engine, Column, String, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.backend.config.settings import settings


Base = declarative_base()


class DocumentRecord(Base):
    __tablename__ = "documents"

    file_id = Column(String, primary_key=True)
    file_name = Column(String, nullable=False)
    s3_uri = Column(Text, nullable=False)
    document_type = Column(String, nullable=True)
    status = Column(String, nullable=False, default="uploaded")
    uploaded_at = Column(DateTime, nullable=False)
    processed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)


class DocumentStore:
    def __init__(self):
        self.engine = create_engine(settings.postgres_url)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)

    def create_document(
        self,
        file_id: str,
        file_name: str,
        s3_uri: str,
        document_type: Optional[str] = None
    ) -> None:
        session = self.SessionLocal()
        try:
            record = DocumentRecord(
                file_id=file_id,
                file_name=file_name,
                s3_uri=s3_uri,
                document_type=document_type,
                status="uploaded",
                uploaded_at=datetime.now(timezone.utc)
            )
            session.add(record)
            session.commit()
        finally:
            session.close()

    def update_status(
        self,
        file_id: str,
        status: str,
        document_type: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> None:
        session = self.SessionLocal()
        try:
            record = session.query(DocumentRecord).filter_by(file_id=file_id).first()
            if not record:
                return

            record.status = status

            if document_type:
                record.document_type = document_type

            if status in ["processed", "registered", "indexed"]:
                record.processed_at = datetime.now(timezone.utc)

            if error_message:
                record.error_message = error_message

            session.commit()
        finally:
            session.close()