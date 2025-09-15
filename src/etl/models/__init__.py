"""
ETL Package for Weekly Document Retrieval Pipeline

This package provides a comprehensive ETL solution for incrementally
retrieving and loading document data into BigQuery using GCP services.
"""

from .etl_models import ETLJobStatus, WatermarkState, DocumentBatch, ETLRunMetrics

__version__ = "1.0.0"
__all__ = [
    'ETLJobStatus',
    'WatermarkState',
    'DocumentBatch',
    'ETLRunMetrics',
]
