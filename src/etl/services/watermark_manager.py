"""
Watermark Manager for ETL Pipeline

Manages watermarks to track the last processed state for each year,
enabling efficient incremental data loading.
"""

from typing import Dict, List, Optional
from datetime import datetime
from google.cloud import bigquery
from google.cloud.exceptions import NotFound

from base import WakalatLogger, alert_bigquery_failure, alert_system_error
from ..models.etl_models import WatermarkState


class WatermarkManager:
    """
    Manages watermarks for incremental ETL processing.

    Watermarks track the last successfully processed page and document
    for each year, enabling incremental processing that resumes from
    the last known good state.
    """

    def __init__(self,
                 project_id: str,
                 dataset_id: str,
                 watermark_table_id: str = "etl_watermarks",
                 credentials_path: Optional[str] = None):
        """
        Initialize the watermark manager.

        Args:
            project_id: GCP project ID
            dataset_id: BigQuery dataset ID
            watermark_table_id: Table name for storing watermarks
            credentials_path: Path to service account JSON (optional)
        """
        self.logger = WakalatLogger("WatermarkManager")

        self.project_id = project_id
        self.dataset_id = dataset_id
        self.watermark_table_id = watermark_table_id

        # Initialize BigQuery client
        if credentials_path:
            self.client = bigquery.Client.from_service_account_json(
                credentials_path, project=project_id
            )
        else:
            self.client = bigquery.Client(project=project_id)

        self.table_ref = self.client.dataset(dataset_id).table(watermark_table_id)

        # Ensure watermark table exists
        self._ensure_watermark_table_exists()

    def _ensure_watermark_table_exists(self):
        """Create watermark table if it doesn't exist."""
        try:
            self.client.get_table(self.table_ref)
            self.logger.info(f"Watermark table {self.watermark_table_id} exists")
        except NotFound:
            self.logger.info(f"Creating watermark table {self.watermark_table_id}")
            self._create_watermark_table()

    def _create_watermark_table(self):
        """Create the watermark tracking table."""
        try:
            schema = [
                bigquery.SchemaField("year", "INTEGER", mode="REQUIRED"),
                bigquery.SchemaField("last_processed_page", "INTEGER", mode="REQUIRED"),
                bigquery.SchemaField("last_document_id", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("last_updated", "TIMESTAMP", mode="REQUIRED"),
                bigquery.SchemaField("total_documents", "INTEGER", mode="REQUIRED", default_value_expression="0"),
                bigquery.SchemaField("is_complete", "BOOLEAN", mode="REQUIRED", default_value_expression="false"),
                bigquery.SchemaField("metadata", "JSON", mode="NULLABLE")
            ]

            table = bigquery.Table(self.table_ref, schema=schema)
            table.description = "ETL pipeline watermarks for tracking incremental processing"

            # Partition by year for better performance
            table.time_partitioning = bigquery.TimePartitioning(
                type_=bigquery.TimePartitioningType.MONTH,
                field="last_updated"
            )

            table = self.client.create_table(table)
            self.logger.info(f"Created watermark table {table.table_id}")

        except Exception as e:
            alert_bigquery_failure(
                operation="create_watermark_table",
                error=e,
                data_context={
                    "table_id": self.watermark_table_id,
                    "dataset_id": self.dataset_id
                }
            )
            raise

    def get_watermark(self, year: int) -> Optional[WatermarkState]:
        """
        Retrieve the watermark state for a specific year.

        Args:
            year: Year to get watermark for

        Returns:
            WatermarkState if found, None otherwise
        """
        try:
            query = f"""
            SELECT 
                year,
                last_processed_page,
                last_document_id,
                last_updated,
                total_documents,
                is_complete
            FROM `{self.project_id}.{self.dataset_id}.{self.watermark_table_id}`
            WHERE year = @year
            ORDER BY last_updated DESC
            LIMIT 1
            """

            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("year", "INT64", year)
                ]
            )

            query_job = self.client.query(query, job_config=job_config)
            results = list(query_job.result())

            if results:
                row = results[0]
                return WatermarkState(
                    year=row.year,
                    last_processed_page=row.last_processed_page,
                    last_document_id=row.last_document_id,
                    last_updated=row.last_updated,
                    total_documents=row.total_documents or 0,
                    is_complete=row.is_complete or False
                )

            return None

        except Exception as e:
            self.logger.error(f"Error retrieving watermark for year {year}: {e}")
            alert_bigquery_failure(
                operation="get_watermark",
                error=e,
                data_context={"year": year}
            )
            raise

    def update_watermark(self, watermark: WatermarkState) -> bool:
        """
        Update or insert watermark state for a year.

        Args:
            watermark: WatermarkState to save

        Returns:
            True if successful
        """
        try:
            # Use MERGE for upsert operation
            merge_query = f"""
            MERGE `{self.project_id}.{self.dataset_id}.{self.watermark_table_id}` AS target
            USING (
                SELECT 
                    @year as year,
                    @last_processed_page as last_processed_page,
                    @last_document_id as last_document_id,
                    @last_updated as last_updated,
                    @total_documents as total_documents,
                    @is_complete as is_complete
            ) AS source
            ON target.year = source.year
            WHEN MATCHED THEN
                UPDATE SET
                    last_processed_page = source.last_processed_page,
                    last_document_id = source.last_document_id,
                    last_updated = source.last_updated,
                    total_documents = source.total_documents,
                    is_complete = source.is_complete
            WHEN NOT MATCHED THEN
                INSERT (year, last_processed_page, last_document_id, last_updated, total_documents, is_complete)
                VALUES (source.year, source.last_processed_page, source.last_document_id, 
                       source.last_updated, source.total_documents, source.is_complete)
            """

            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("year", "INT64", watermark.year),
                    bigquery.ScalarQueryParameter("last_processed_page", "INT64", watermark.last_processed_page),
                    bigquery.ScalarQueryParameter("last_document_id", "STRING", watermark.last_document_id),
                    bigquery.ScalarQueryParameter("last_updated", "TIMESTAMP", watermark.last_updated),
                    bigquery.ScalarQueryParameter("total_documents", "INT64", watermark.total_documents),
                    bigquery.ScalarQueryParameter("is_complete", "BOOL", watermark.is_complete)
                ]
            )

            query_job = self.client.query(merge_query, job_config=job_config)
            query_job.result()  # Wait for completion

            self.logger.info(f"Updated watermark for year {watermark.year}: page {watermark.last_processed_page}")
            return True

        except Exception as e:
            self.logger.error(f"Error updating watermark for year {watermark.year}: {e}")
            alert_bigquery_failure(
                operation="update_watermark",
                error=e,
                data_context=watermark.to_dict()
            )
            raise

    def get_all_watermarks(self) -> Dict[int, WatermarkState]:
        """
        Get watermarks for all years.

        Returns:
            Dictionary mapping year to WatermarkState
        """
        try:
            query = f"""
            SELECT 
                year,
                last_processed_page,
                last_document_id,
                last_updated,
                total_documents,
                is_complete
            FROM `{self.project_id}.{self.dataset_id}.{self.watermark_table_id}`
            ORDER BY year DESC
            """

            query_job = self.client.query(query)
            results = list(query_job.result())

            watermarks = {}
            for row in results:
                watermarks[row.year] = WatermarkState(
                    year=row.year,
                    last_processed_page=row.last_processed_page,
                    last_document_id=row.last_document_id,
                    last_updated=row.last_updated,
                    total_documents=row.total_documents or 0,
                    is_complete=row.is_complete or False
                )

            return watermarks

        except Exception as e:
            self.logger.error(f"Error retrieving all watermarks: {e}")
            alert_bigquery_failure(
                operation="get_all_watermarks",
                error=e
            )
            raise

    def reset_watermark(self, year: int) -> bool:
        """
        Reset watermark for a year (useful for reprocessing).

        Args:
            year: Year to reset

        Returns:
            True if successful
        """
        try:
            watermark = WatermarkState(
                year=year,
                last_processed_page=0,
                last_document_id=None,
                last_updated=datetime.utcnow(),
                total_documents=0,
                is_complete=False
            )

            return self.update_watermark(watermark)

        except Exception as e:
            alert_system_error(
                component="watermark_reset",
                error=e,
                context={"year": year}
            )
            raise

    def mark_year_complete(self, year: int) -> bool:
        """
        Mark a year as completely processed.

        Args:
            year: Year to mark as complete

        Returns:
            True if successful
        """
        try:
            existing_watermark = self.get_watermark(year)
            if existing_watermark:
                existing_watermark.is_complete = True
                existing_watermark.last_updated = datetime.utcnow()
                return self.update_watermark(existing_watermark)
            else:
                self.logger.warning(f"Cannot mark year {year} complete - no watermark found")
                return False

        except Exception as e:
            alert_system_error(
                component="mark_year_complete",
                error=e,
                context={"year": year}
            )
            raise
