"""
Cloud Function Handler for ETL Pipeline

This module provides the entry point for the Cloud Function that handles
the weekly ETL pipeline execution triggered by Cloud Scheduler via Pub/Sub.
"""

import os
import json
import base64
from typing import Dict, Any, List

from base import WakalatLogger, alert_system_error
from src.data import DocRetrieverConstants
from src.etl import ETLJobStatus, ETLOrchestrator
from dotenv import load_dotenv

load_dotenv()


def main(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Cloud Function entry point for ETL pipeline.

    This function is triggered by Cloud Scheduler via Pub/Sub messages.
    It runs the incremental ETL pipeline to check for new documents
    and load them into BigQuery.

    Args:
        event: Pub/Sub event data
        context: Cloud Function context

    Returns:
        Dictionary with execution results
    """
    logger = WakalatLogger("ETLCloudFunction")

    try:
        logger.info("ETL Cloud Function triggered")

        # Parse Pub/Sub message
        pubsub_message = event.get('data')
        message_data = {}

        if pubsub_message:
            try:
                # Decode base64 message
                decoded_data = base64.b64decode(pubsub_message).decode('utf-8')
                message_data = json.loads(decoded_data)
                logger.info(f"Received message data: {message_data}")
            except Exception as e:
                logger.warning(f"Could not parse Pub/Sub message data: {e}")
                # Continue with default parameters

        # Extract configuration from environment variables and message
        config = _get_etl_configuration(message_data)

        # Validate required configuration
        missing_config = _validate_configuration(config)
        if missing_config:
            error_msg = f"Missing required configuration: {', '.join(missing_config)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "status": ETLJobStatus.FAILED.value
            }

        # Initialize ETL orchestrator
        orchestrator = ETLOrchestrator(
            project_id=config['project_id'],
            dataset_id=config['dataset_id'],
            documents_table_id=config['documents_table_id'],
            credentials_path=config.get('credentials_path'),
            max_pages_per_year=config.get('max_pages_per_year', 50)
        )

        # Determine years to process
        years = config.get('years')
        if years is None:
            years = list(DocRetrieverConstants.get_year_range())
            logger.info(f"Using default year range: {years}")
        else:
            logger.info(f"Using specified years: {years}")

        # Run the ETL pipeline
        logger.info("Starting ETL pipeline execution")

        metrics = orchestrator.run_incremental_etl(
            years=years,
            max_documents_per_run=config.get('max_documents_per_run')
        )

        # Prepare response
        response = {
            "success": metrics.status in [ETLJobStatus.SUCCESS, ETLJobStatus.PARTIAL_SUCCESS],
            "job_id": metrics.job_id,
            "status": metrics.status.value,
            "start_time": metrics.start_time.isoformat(),
            "end_time": metrics.end_time.isoformat() if metrics.end_time else None,
            "duration_seconds": metrics.duration_seconds,
            "years_processed": metrics.years_processed,
            "documents_found": metrics.total_documents_found,
            "documents_added": metrics.total_documents_added,
            "documents_skipped": metrics.total_documents_skipped,
            "errors": metrics.errors,
            "processing_details": metrics.processing_details
        }

        if response["success"]:
            logger.info(f"ETL pipeline completed successfully: {metrics.job_id}")
            logger.info(f"Documents processed: {metrics.total_documents_found} found, "
                        f"{metrics.total_documents_added} added")
        else:
            logger.error(f"ETL pipeline completed with errors: {metrics.job_id}")
            logger.error(f"Errors: {metrics.errors}")

        return response

    except Exception as e:
        error_msg = f"ETL Cloud Function failed: {str(e)}"
        logger.error(error_msg)

        # Send alert for function failures
        alert_system_error(
            component="ETL_cloud_function",
            error=e,
            context={
                "event": event,
                "function_name": context.function_name if hasattr(context, 'function_name') else 'unknown',
                "execution_id": context.request_id if hasattr(context, 'request_id') else 'unknown'
            }
        )

        return {
            "success": False,
            "error": error_msg,
            "status": ETLJobStatus.FAILED.value,
            "execution_id": context.request_id if hasattr(context, 'request_id') else None
        }


def _get_etl_configuration(message_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract ETL configuration from environment variables and message data.

    Args:
        message_data: Data from Pub/Sub message

    Returns:
        Dictionary with configuration values
    """
    config = {
        # Required configuration
        'project_id': os.getenv('GCP.PROJECT_ID') or message_data.get('project_id'),
        'dataset_id': os.getenv('GCP.DATASET_ID') or message_data.get('dataset_id'),
        'documents_table_id': os.getenv('GCP.TABLE_ID', 'documents') or message_data.get('documents_table_id'),

        # Optional configuration
        'credentials_path': os.getenv('GCP.CREDENTIALS_PATH') or message_data.get('credentials_path'),
        'max_pages_per_year': int(os.getenv('ETL_MAX_PAGES_PER_YEAR', '50')) or message_data.get('max_pages_per_year',
                                                                                                 50),
        'max_documents_per_run': message_data.get('max_documents_per_run'),
        'years': message_data.get('years')
    }

    # Convert string years to integers if provided
    if config['years'] and isinstance(config['years'], list):
        try:
            config['years'] = [int(year) for year in config['years']]
        except (ValueError, TypeError):
            config['years'] = None

    return config


def _validate_configuration(config: Dict[str, Any]) -> List[str]:
    """
    Validate required configuration parameters.

    Args:
        config: Configuration dictionary

    Returns:
        List of missing required parameters
    """
    required_params = ['project_id', 'dataset_id', 'documents_table_id']
    missing = []

    for param in required_params:
        if not config.get(param):
            missing.append(param)

    return missing


# Additional helper functions for testing and debugging
def test_etl_function(test_data: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Test function for local development and debugging.

    Args:
        test_data: Optional test data to simulate Pub/Sub message

    Returns:
        Function execution results
    """

    # Create mock event and context for testing
    class MockContext:
        def __init__(self):
            self.function_name = "test_etl_function"
            self.request_id = "test_request_123"

    if test_data is None:
        test_data = {
            "message": "Weekly ETL pipeline execution",
            "years": [2025],  # Test with single year
            "max_pages_per_year": 5,  # Limit for testing
            "max_documents_per_run": 100
        }

    # Encode test data as base64 (like Pub/Sub does)
    encoded_data = base64.b64encode(json.dumps(test_data).encode('utf-8')).decode('utf-8')

    event = {
        'data': encoded_data,
        'attributes': {
            'trigger': 'cloud_scheduler'
        }
    }

    context = MockContext()

    return main(event, context)


def get_etl_status() -> Dict[str, Any]:
    """
    Get the status of recent ETL jobs.

    This can be called as a separate endpoint or function to check
    the status of recent ETL pipeline executions.

    Returns:
        Dictionary with recent job statuses
    """
    logger = WakalatLogger("ETLStatus")

    try:
        # Get configuration
        config = _get_etl_configuration({})

        # Validate required config for status check
        missing_config = _validate_configuration(config)
        if missing_config:
            return {
                "success": False,
                "error": f"Missing required configuration: {', '.join(missing_config)}"
            }

        # Initialize orchestrator
        orchestrator = ETLOrchestrator(
            project_id=config['project_id'],
            dataset_id=config['dataset_id'],
            documents_table_id=config['documents_table_id'],
            credentials_path=config.get('credentials_path')
        )

        # Get recent job statuses
        recent_jobs = orchestrator.get_recent_jobs(limit=10)

        # Get watermark states
        watermarks = orchestrator.watermark_manager.get_all_watermarks()
        watermark_summary = {
            year: {
                "last_processed_page": state.last_processed_page,
                "total_documents": state.total_documents,
                "is_complete": state.is_complete,
                "last_updated": state.last_updated.isoformat()
            }
            for year, state in watermarks.items()
        }

        return {
            "success": True,
            "recent_jobs": recent_jobs,
            "watermark_states": watermark_summary,
            "checked_at": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error getting ETL status: {e}")
        return {
            "success": False,
            "error": str(e)
        }


# For local testing
if __name__ == "__main__":
    import sys
    from datetime import datetime

    if len(sys.argv) > 1 and sys.argv[1] == "test":
        print("Running ETL function test...")
        result = test_etl_function()
        print("Test result:", json.dumps(result, indent=2))

    elif len(sys.argv) > 1 and sys.argv[1] == "status":
        print("Getting ETL status...")
        result = get_etl_status()
        print("Status result:", json.dumps(result, indent=2))

    else:
        print("Usage:")
        print("  python cloud_function_handler.py test    # Run test")
        print("  python cloud_function_handler.py status  # Get status")
