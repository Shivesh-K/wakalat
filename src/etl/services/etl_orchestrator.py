"""
ETL Orchestrator

Coordinates the entire ETL process including incremental document checking,
watermark management, BigQuery loading, and document parsing.
"""
import json
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, UTC

from base import WakalatLogger, alert_system_error
from src.data import BigQueryDocumentWriter, ComprehensiveDocRetriever, DocRetrieverConstants, DocumentParser
from src.etl.models import ETLRunMetrics, ETLJobStatus, DocumentBatch
from .watermark_manager import WatermarkManager
from .incremental_checker import IncrementalDocumentChecker


class ETLOrchestrator:
    """
    Orchestrates the complete ETL pipeline process.

    Manages the workflow of checking for new documents, validating data,
    updating watermarks, loading data into BigQuery, and parsing document content.
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

        # Initialize document parser
        self.document_parser = DocumentParser(
            project_id=project_id,
            dataset_id=dataset_id,
            credentials_path=credentials_path
        )

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
                    bigquery.SchemaField("total_documents_parsed", "INTEGER", mode="REQUIRED"),
                    bigquery.SchemaField("total_parsing_failures", "INTEGER", mode="REQUIRED"),
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
                            max_documents_per_run: Optional[int] = None,
                            skip_parsing: bool = False) -> ETLRunMetrics:
        """
        Run the complete incremental ETL pipeline with document parsing.

        Args:
            years: List of years to process (default: uses constants)
            max_documents_per_run: Maximum documents to process in this run
            skip_parsing: Whether to skip the parsing phase

        Returns:
            ETLRunMetrics with job results
        """
        job_id = f"etl_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

        metrics = ETLRunMetrics(
            job_id=job_id,
            start_time=datetime.now(UTC),
            status=ETLJobStatus.RUNNING
        )

        # Add parsing metrics to the metrics object
        metrics.total_documents_parsed = 0
        metrics.total_parsing_failures = 0

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

            # Phase 2: Load new documents into BigQuery and fetch details
            self.logger.info(f"Phase 2: Loading {total_documents_to_process} new documents into BigQuery")

            processed_document_ids = []  # Track successfully processed documents for parsing

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

                        if success:
                            # Fetch document details for each document
                            year_processed_doc_ids = []
                            for doc in all_year_documents:
                                doc_id = doc['doc_id']
                                try:
                                    details = self.doc_retriever.fetch_document_details(doc_id)
                                    if details:
                                        detail_success = self.bigquery_writer.insert_document_details(details)
                                        if detail_success:
                                            year_processed_doc_ids.append(doc_id)
                                            self.logger.debug(f"Successfully fetched and saved details for {doc_id}")
                                        else:
                                            self.logger.warning(f"Failed to save details for {doc_id}")
                                    else:
                                        self.logger.warning(f"Failed to fetch details for {doc_id}")
                                except Exception as e:
                                    self.logger.error(f"Error processing details for {doc_id}: {e}")

                            documents_added = len(all_year_documents)
                            processed_document_ids.extend(year_processed_doc_ids)
                            self.logger.info(f"Successfully loaded {documents_added} documents for year {year}")
                            self.logger.info(
                                f"Successfully fetched details for {len(year_processed_doc_ids)} documents")
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

            # Phase 3: Parse document content
            if not skip_parsing and processed_document_ids:
                self.logger.info(f"Phase 3: Parsing {len(processed_document_ids)} document contents")

                parsing_results = self._parse_documents(processed_document_ids)
                metrics.total_documents_parsed = parsing_results['successful']
                metrics.total_parsing_failures = parsing_results['failed']

                self.logger.info(f"Parsing completed: {parsing_results['successful']} successful, "
                                 f"{parsing_results['failed']} failed")

                # Add parsing errors to metrics
                if parsing_results['errors']:
                    for error in parsing_results['errors']:
                        metrics.add_error(f"Parsing error: {error}")

            elif skip_parsing:
                self.logger.info("Phase 3: Skipping document parsing as requested")
            else:
                self.logger.info("Phase 3: No documents to parse")

            # Determine final job status
            if metrics.total_documents_added == total_documents_to_process:
                if not skip_parsing and metrics.total_parsing_failures > 0:
                    final_status = ETLJobStatus.PARTIAL_SUCCESS
                else:
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

            if not skip_parsing:
                self.logger.info(f"Parsing: {metrics.total_documents_parsed} successful, "
                                 f"{metrics.total_parsing_failures} failed")

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

    def _parse_documents(self, document_ids: List[str]) -> Dict[str, Any]:
        """
        Parse document contents for the given document IDs.

        Args:
            document_ids: List of document IDs to parse

        Returns:
            Dict with parsing results summary
        """
        parsing_results = {
            'successful': 0,
            'failed': 0,
            'errors': []
        }

        self.logger.info(f"Starting parsing of {len(document_ids)} documents")

        for i, doc_id in enumerate(document_ids, 1):
            try:
                self.logger.debug(f"Parsing document {i}/{len(document_ids)}: {doc_id}")

                # Check if document is already parsed
                if self.document_parser.is_document_parsed(doc_id):
                    self.logger.debug(f"Document {doc_id} already parsed, skipping")
                    parsing_results['successful'] += 1
                    continue

                # Parse the document
                parse_result = self.document_parser.parse_document(doc_id)

                if parse_result and parse_result.get('success', False):
                    parsing_results['successful'] += 1
                    self.logger.debug(f"Successfully parsed document {doc_id}")
                else:
                    parsing_results['failed'] += 1
                    error_msg = parse_result.get('error',
                                                 'Unknown parsing error') if parse_result else 'Parse returned None'
                    parsing_results['errors'].append(f"Doc {doc_id}: {error_msg}")
                    self.logger.warning(f"Failed to parse document {doc_id}: {error_msg}")

            except Exception as e:
                parsing_results['failed'] += 1
                error_msg = f"Exception parsing document {doc_id}: {str(e)}"
                parsing_results['errors'].append(error_msg)
                self.logger.error(error_msg)

            # Progress logging
            if i % 10 == 0:
                self.logger.info(f"Parsing progress: {i}/{len(document_ids)} documents processed")

        success_rate = (parsing_results['successful'] / len(document_ids)) * 100 if document_ids else 0
        self.logger.info(f"Parsing completed: {parsing_results['successful']}/{len(document_ids)} "
                         f"successful ({success_rate:.1f}%)")

        return parsing_results

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

            # Add parsing metrics if they exist
            if hasattr(metrics, 'total_documents_parsed'):
                metrics_data['total_documents_parsed'] = metrics.total_documents_parsed
                metrics_data['total_parsing_failures'] = metrics.total_parsing_failures
            else:
                metrics_data['total_documents_parsed'] = 0
                metrics_data['total_parsing_failures'] = 0

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
                    "total_documents_parsed": getattr(row, 'total_documents_parsed', 0),
                    "total_parsing_failures": getattr(row, 'total_parsing_failures', 0),
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
                total_documents_parsed,
                total_parsing_failures,
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
                    "total_documents_parsed": getattr(row, 'total_documents_parsed', 0),
                    "total_parsing_failures": getattr(row, 'total_parsing_failures', 0),
                    "duration_seconds": row.duration_seconds
                })

            return jobs

        except Exception as e:
            self.logger.error(f"Error retrieving recent jobs: {e}")
            return []
