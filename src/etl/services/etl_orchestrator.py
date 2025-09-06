"""
ETL Orchestrator

Coordinates the entire ETL process including incremental document checking,
watermark management, and BigQuery loading.
"""
import json
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime

from base import WakalatLogger, alert_system_error
from src.data import BigQueryDocumentWriter, DocRetrieverConstants
from ..models.etl_models import ETLRunMetrics, ETLJobStatus, DocumentBatch
from ..services.watermark_manager import WatermarkManager
from ..services.incremental_checker import IncrementalDocumentChecker
from ...data.document_retriever import ComprehensiveDocRetriever


class ETLOrchestrator:
    """
    Orchestrates the complete ETL pipeline process.

    Manages the workflow of checking for new documents, validating data,
    updating watermarks, and loading data into BigQuery.
    """

    def __init__(self,
                 project_id: str,
                 dataset_id: str,
                 documents_table_id: str,
                 credentials_path: Optional[str] = None,
                 max_pages_per_year: int = 50):
        """
        Initialize the ETL orchestrator.

        Args:
            project_id: GCP project ID
            dataset_id: BigQuery dataset ID
            documents_table_id: Main documents table name
            credentials_path: Path to service account JSON (optional)
            max_pages_per_year: Maximum pages to process per year per run
        """
        self.logger = WakalatLogger("ETLOrchestrator")

        self.project_id = project_id
        self.dataset_id = dataset_id
        self.documents_table_id = documents_table_id
        self.max_pages_per_year = max_pages_per_year

        # Initialize components
        self.watermark_manager = WatermarkManager(
            project_id=project_id,
            dataset_id=dataset_id,
            credentials_path=credentials_path
        )

        self.incremental_checker = IncrementalDocumentChecker(
            project_id=project_id,
            dataset_id=dataset_id,
            documents_table_id=documents_table_id,
            watermark_manager=self.watermark_manager,
            credentials_path=credentials_path
        )

        self.bigquery_writer = BigQueryDocumentWriter(
            project_id=project_id,
            dataset_id=dataset_id,
            table_id=documents_table_id,
            credentials_path=credentials_path
        )

        self.doc_retriever = ComprehensiveDocRetriever()

        # Create ETL job metrics table if needed
        self._ensure_metrics_table_exists()

    def _ensure_metrics_table_exists(self):
        """Ensure ETL metrics table exists for tracking job runs."""
        try:
            from google.cloud import bigquery
            from google.cloud.exceptions import NotFound

            client = self.bigquery_writer.client
            metrics_table_ref = client.dataset(self.dataset_id).table("etl_job_metrics")

            try:
                client.get_table(metrics_table_ref)
                self.logger.info("ETL metrics table exists")
            except NotFound:
                self.logger.info("Creating ETL metrics table")

                schema = [
                    bigquery.SchemaField("job_id", "STRING", mode="REQUIRED"),
                    bigquery.SchemaField("start_time", "TIMESTAMP", mode="REQUIRED"),
                    bigquery.SchemaField("end_time", "TIMESTAMP", mode="NULLABLE"),
                    bigquery.SchemaField("status", "STRING", mode="REQUIRED"),
                    bigquery.SchemaField("years_processed", "INTEGER", mode="REPEATED"),
                    bigquery.SchemaField("total_documents_found", "INTEGER", mode="REQUIRED"),
                    bigquery.SchemaField("total_documents_added", "INTEGER", mode="REQUIRED"),
                    bigquery.SchemaField("total_documents_skipped", "INTEGER", mode="REQUIRED"),
                    bigquery.SchemaField("errors", "STRING", mode="REPEATED"),
                    bigquery.SchemaField("processing_details", "JSON", mode="NULLABLE"),
                    bigquery.SchemaField("duration_seconds", "FLOAT", mode="NULLABLE")
                ]

                table = bigquery.Table(metrics_table_ref, schema=schema)
                table.description = "ETL pipeline job execution metrics"

                # Partition by start_time for better performance
                table.time_partitioning = bigquery.TimePartitioning(
                    type_=bigquery.TimePartitioningType.DAY,
                    field="start_time"
                )

                client.create_table(table)
                self.logger.info("Created ETL metrics table")

        except Exception as e:
            self.logger.warning(f"Could not ensure metrics table exists: {e}")
            # Continue without metrics table - not critical for core functionality

    def run_incremental_etl(self,
                            years: Optional[List[int]] = None,
                            max_documents_per_run: Optional[int] = None) -> ETLRunMetrics:
        """
        Run the complete incremental ETL pipeline.

        Args:
            years: List of years to process (default: uses constants)
            max_documents_per_run: Maximum documents to process in this run

        Returns:
            ETLRunMetrics with job results
        """
        job_id = f"etl_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

        metrics = ETLRunMetrics(
            job_id=job_id,
            start_time=datetime.utcnow(),
            status=ETLJobStatus.RUNNING
        )

        try:
            self.logger.info(f"Starting ETL job {job_id}")

            # Determine years to process
            if years is None:
                years = list(DocRetrieverConstants.get_year_range())

            self.logger.info(f"Processing years: {years}")

            # Phase 1: Check for incremental updates
            self.logger.info("Phase 1: Checking for incremental updates")
            incremental_results = self.incremental_checker.check_incremental_updates(
                years=years,
                max_pages_per_year=self.max_pages_per_year
            )

            # Generate processing summary
            summary = self.incremental_checker.get_processing_summary(incremental_results)
            self.logger.info(f"Incremental check summary: {summary}")

            # Check if we should limit documents processed
            total_documents_to_process = summary['total_new_documents']
            if max_documents_per_run and total_documents_to_process > max_documents_per_run:
                self.logger.info(f"Limiting documents to {max_documents_per_run} "
                                 f"(found {total_documents_to_process})")
                incremental_results = self._limit_documents(incremental_results, max_documents_per_run)
                total_documents_to_process = max_documents_per_run

            if total_documents_to_process == 0:
                self.logger.info("No new documents found - ETL job complete")
                metrics.complete_job(ETLJobStatus.SUCCESS)
                self._save_metrics(metrics)
                return metrics

            # Phase 2: Load new documents into BigQuery
            self.logger.info(f"Phase 2: Loading {total_documents_to_process} new documents into BigQuery")

            for year, batches in incremental_results.items():
                if not batches:
                    continue

                try:
                    documents_found = sum(len(batch) for batch in batches)
                    documents_added = 0
                    documents_skipped = 0

                    self.logger.info(f"Processing {documents_found} documents for year {year}")

                    # Combine all documents for this year
                    all_year_documents = []
                    for batch in batches:
                        all_year_documents.extend(batch.documents)

                    if all_year_documents:
                        # Insert documents into BigQuery
                        success = self.bigquery_writer.insert_rows(all_year_documents)

                        for doc in all_year_documents:
                            self.bigquery_writer.insert_document_details(self.doc_retriever.fetch_document_details(doc['doc_id']))

                        if success:
                            documents_added = len(all_year_documents)
                            self.logger.info(f"Successfully loaded {documents_added} documents for year {year}")
                        else:
                            documents_skipped = len(all_year_documents)
                            metrics.add_error(f"Failed to load documents for year {year}")

                    # Update metrics for this year
                    metrics.add_year_metrics(
                        year=year,
                        found=documents_found,
                        added=documents_added,
                        skipped=documents_skipped
                    )

                except Exception as e:
                    error_msg = f"Error processing year {year}: {str(e)}"
                    self.logger.error(error_msg)
                    metrics.add_error(error_msg)

                    # Still try to update metrics for partial progress
                    documents_found = sum(len(batch) for batch in batches)
                    metrics.add_year_metrics(
                        year=year,
                        found=documents_found,
                        added=0,
                        skipped=documents_found
                    )

            # Determine final job status
            if metrics.total_documents_added == total_documents_to_process:
                final_status = ETLJobStatus.SUCCESS
            elif metrics.total_documents_added > 0:
                final_status = ETLJobStatus.PARTIAL_SUCCESS
            else:
                final_status = ETLJobStatus.FAILED

            metrics.complete_job(final_status)

            self.logger.info(f"ETL job {job_id} completed with status {final_status.value}")
            self.logger.info(f"Documents: {metrics.total_documents_found} found, "
                             f"{metrics.total_documents_added} added, "
                             f"{metrics.total_documents_skipped} skipped")

            # Save metrics
            self._save_metrics(metrics)

            return metrics

        except Exception as e:
            error_msg = f"ETL job {job_id} failed: {str(e)}"
            self.logger.error(error_msg)
            metrics.add_error(error_msg)
            metrics.complete_job(ETLJobStatus.FAILED)

            alert_system_error(
                component="ETL_orchestrator",
                error=e,
                context={
                    "job_id": job_id,
                    "years": years,
                    "max_documents_per_run": max_documents_per_run
                }
            )

            # Try to save metrics even for failed jobs
            try:
                self._save_metrics(metrics)
            except Exception as save_error:
                self.logger.error(f"Could not save metrics for failed job: {save_error}")

            return metrics

    def _limit_documents(self,
                         incremental_results: Dict[int, List[DocumentBatch]],
                         max_documents: int) -> Dict[int, List[DocumentBatch]]:
        """
        Limit the number of documents to process across all years.

        Args:
            incremental_results: Original results
            max_documents: Maximum documents to keep

        Returns:
            Limited results
        """
        limited_results = {}
        documents_remaining = max_documents

        # Process years in order, taking documents until limit is reached
        for year in sorted(incremental_results.keys()):
            if documents_remaining <= 0:
                limited_results[year] = []
                continue

            year_batches = incremental_results[year]
            limited_batches = []

            for batch in year_batches:
                if documents_remaining <= 0:
                    break

                if len(batch.documents) <= documents_remaining:
                    # Take entire batch
                    limited_batches.append(batch)
                    documents_remaining -= len(batch.documents)
                else:
                    # Take partial batch
                    limited_documents = batch.documents[:documents_remaining]
                    limited_batch = DocumentBatch(
                        year=batch.year,
                        page=batch.page,
                        documents=limited_documents,
                        retrieved_at=batch.retrieved_at
                    )
                    limited_batches.append(limited_batch)
                    documents_remaining = 0
                    break

            limited_results[year] = limited_batches

        return limited_results

    def _save_metrics(self, metrics: ETLRunMetrics):
        """Save job metrics to BigQuery."""
        try:
            metrics_data = metrics.to_dict()
            if 'processing_details' in metrics_data and not isinstance(metrics_data['processing_details'], str):
                processing_details = metrics_data['processing_details']
                metrics_data['processing_details'] = json.dumps(processing_details)

            # Try to insert metrics
            from google.cloud import bigquery
            client = self.bigquery_writer.client
            table_ref = client.dataset(self.dataset_id).table("etl_job_metrics")

            errors = client.insert_rows_json(table_ref, [metrics_data])

            if errors:
                self.logger.warning(f"Errors saving metrics: {errors}")
            else:
                self.logger.info(f"Saved metrics for job {metrics.job_id}")

        except Exception as e:
            self.logger.warning(f"Could not save job metrics: {e}")
            # Don't fail the job if metrics saving fails

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the status of a specific ETL job.

        Args:
            job_id: Job ID to look up

        Returns:
            Job metrics dictionary if found, None otherwise
        """
        try:
            from google.cloud import bigquery
            client = self.bigquery_writer.client

            query = f"""
            SELECT *
            FROM `{self.project_id}.{self.dataset_id}.etl_job_metrics`
            WHERE job_id = @job_id
            ORDER BY start_time DESC
            LIMIT 1
            """

            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("job_id", "STRING", job_id)
                ]
            )

            query_job = client.query(query, job_config=job_config)
            results = list(query_job.result())

            if results:
                row = results[0]
                return {
                    "job_id": row.job_id,
                    "start_time": row.start_time.isoformat(),
                    "end_time": row.end_time.isoformat() if row.end_time else None,
                    "status": row.status,
                    "years_processed": list(row.years_processed) if row.years_processed else [],
                    "total_documents_found": row.total_documents_found,
                    "total_documents_added": row.total_documents_added,
                    "total_documents_skipped": row.total_documents_skipped,
                    "errors": list(row.errors) if row.errors else [],
                    "duration_seconds": row.duration_seconds
                }

            return None

        except Exception as e:
            self.logger.error(f"Error retrieving job status for {job_id}: {e}")
            return None

    def get_recent_jobs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent ETL job statuses.

        Args:
            limit: Maximum number of jobs to return

        Returns:
            List of job metrics dictionaries
        """
        try:
            from google.cloud import bigquery
            client = self.bigquery_writer.client

            query = f"""
            SELECT 
                job_id,
                start_time,
                end_time,
                status,
                total_documents_found,
                total_documents_added,
                duration_seconds
            FROM `{self.project_id}.{self.dataset_id}.etl_job_metrics`
            ORDER BY start_time DESC
            LIMIT @limit
            """

            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("limit", "INT64", limit)
                ]
            )

            query_job = client.query(query, job_config=job_config)
            results = list(query_job.result())

            jobs = []
            for row in results:
                jobs.append({
                    "job_id": row.job_id,
                    "start_time": row.start_time.isoformat(),
                    "end_time": row.end_time.isoformat() if row.end_time else None,
                    "status": row.status,
                    "total_documents_found": row.total_documents_found,
                    "total_documents_added": row.total_documents_added,
                    "duration_seconds": row.duration_seconds
                })

            return jobs

        except Exception as e:
            self.logger.error(f"Error retrieving recent jobs: {e}")
            return []