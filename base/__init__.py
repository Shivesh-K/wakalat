"""
Base package for logging, utilities, and alerting system.
"""

from .logger import WakalatLogger
from .alert_system import (
    WakalatAlertSystem,
    AlertSeverity,
    AlertType,
    get_alert_system,
    send_alert,
    alert_document_retrieval_failure,
    alert_document_id_extraction_failure,
    alert_bigquery_failure,
    alert_data_validation_failure,
    alert_rate_limit_exceeded,
    alert_system_error
)

__version__ = "1.0.0"
__all__ = [
    'WakalatLogger',
    'WakalatAlertSystem',
    'AlertSeverity',
    'AlertType',
    'get_alert_system',
    'send_alert',
    'alert_document_retrieval_failure',
    'alert_document_id_extraction_failure',
    'alert_bigquery_failure',
    'alert_data_validation_failure',
    'alert_rate_limit_exceeded',
    'alert_system_error'
]