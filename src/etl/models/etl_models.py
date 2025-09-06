"""
Data models for ETL pipeline operations.

These models define the structure for tracking ETL jobs, watermarks,
and document batches throughout the pipeline.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum


class ETLJobStatus(Enum):
    """Status of ETL job execution."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"


@dataclass
class WatermarkState:
    """Represents the current watermark state for a year."""
    year: int
    last_processed_page: int
    last_document_id: Optional[str] = None
    last_updated: datetime = field(default_factory=datetime.utcnow)
    total_documents: int = 0
    is_complete: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for BigQuery storage."""
        return {
            "year": self.year,
            "last_processed_page": self.last_processed_page,
            "last_document_id": self.last_document_id,
            "last_updated": self.last_updated.isoformat(),
            "total_documents": self.total_documents,
            "is_complete": self.is_complete
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WatermarkState':
        """Create from dictionary loaded from BigQuery."""
        return cls(
            year=data['year'],
            last_processed_page=data['last_processed_page'],
            last_document_id=data.get('last_document_id'),
            last_updated=datetime.fromisoformat(data['last_updated'].replace('Z', '+00:00')),
            total_documents=data.get('total_documents', 0),
            is_complete=data.get('is_complete', False)
        )


@dataclass
class DocumentBatch:
    """Represents a batch of documents to be processed."""
    year: int
    page: int
    documents: List[Dict[str, Any]]
    retrieved_at: datetime = field(default_factory=datetime.utcnow)

    def __len__(self) -> int:
        return len(self.documents)

    def is_empty(self) -> bool:
        return len(self.documents) == 0

    def get_document_ids(self) -> List[str]:
        """Extract document IDs from the batch."""
        return [doc['doc_id'] for doc in self.documents if 'doc_id' in doc]


@dataclass
class ETLRunMetrics:
    """Metrics and results from an ETL run."""
    job_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    status: ETLJobStatus = ETLJobStatus.PENDING
    years_processed: List[int] = field(default_factory=list)
    total_documents_found: int = 0
    total_documents_added: int = 0
    total_documents_skipped: int = 0
    errors: List[str] = field(default_factory=list)
    processing_details: Dict[int, Dict] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate job duration in seconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None

    @property
    def is_complete(self) -> bool:
        """Check if the job is complete."""
        return self.status in [ETLJobStatus.SUCCESS, ETLJobStatus.FAILED, ETLJobStatus.PARTIAL_SUCCESS]

    def add_year_metrics(self, year: int, found: int, added: int, skipped: int):
        """Add metrics for a specific year."""
        self.processing_details[year] = {
            "documents_found": found,
            "documents_added": added,
            "documents_skipped": skipped,
            "processed_at": datetime.utcnow().isoformat()
        }
        self.total_documents_found += found
        self.total_documents_added += added
        self.total_documents_skipped += skipped

        if year not in self.years_processed:
            self.years_processed.append(year)

    def add_error(self, error: str):
        """Add an error to the run."""
        self.errors.append(f"{datetime.utcnow().isoformat()}: {error}")
        if self.status == ETLJobStatus.RUNNING:
            self.status = ETLJobStatus.PARTIAL_SUCCESS

    def complete_job(self, status: ETLJobStatus):
        """Mark the job as complete with final status."""
        self.status = status
        self.end_time = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for BigQuery storage."""
        return {
            "job_id": self.job_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "status": self.status.value,
            "years_processed": self.years_processed,
            "total_documents_found": self.total_documents_found,
            "total_documents_added": self.total_documents_added,
            "total_documents_skipped": self.total_documents_skipped,
            "errors": self.errors,
            "processing_details": self.processing_details,
            "duration_seconds": self.duration_seconds
        }
