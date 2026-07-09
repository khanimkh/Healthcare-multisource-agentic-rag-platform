from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

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

            if status in ["registered", "indexed"]:
                record.processed_at = datetime.now(timezone.utc)

            if error_message:
                record.error_message = error_message

            session.commit()
        finally:
            session.close()

    def list_indexed_document_records(self) -> List[Dict[str, str]]:
        session = self.SessionLocal()
        try:
            records = (
                session.query(DocumentRecord)
                .filter(DocumentRecord.status.in_(["indexed", "registered"]))
                .all()
            )

            return [
                {"file_id": record.file_id, "file_name": record.file_name}
                for record in records
            ]
        finally:
            session.close()

    def get_document(self, file_id: str) -> Optional[Dict[str, Any]]:
        session = self.SessionLocal()
        try:
            record = session.query(DocumentRecord).filter_by(file_id=file_id).first()

            if not record:
                return None

            return {
                "file_id": record.file_id,
                "file_name": record.file_name,
                "s3_uri": record.s3_uri,
                "document_type": record.document_type,
                "status": record.status
            }
        finally:
            session.close()

    def delete_document(self, file_id: str) -> bool:
        session = self.SessionLocal()
        try:
            record = session.query(DocumentRecord).filter_by(file_id=file_id).first()

            if not record:
                return False

            session.delete(record)
            session.commit()
            return True
        finally:
            session.close()

    def list_all_documents(self) -> List[Dict[str, Any]]:
        session = self.SessionLocal()
        try:
            records = (
                session.query(DocumentRecord)
                .order_by(DocumentRecord.uploaded_at.desc())
                .all()
            )

            return [
                {
                    "file_id": record.file_id,
                    "file_name": record.file_name,
                    "document_type": record.document_type,
                    "status": record.status,
                    "uploaded_at": record.uploaded_at.isoformat() if record.uploaded_at else None,
                    "processed_at": record.processed_at.isoformat() if record.processed_at else None,
                    "error_message": record.error_message
                }
                for record in records
            ]
        finally:
            session.close()