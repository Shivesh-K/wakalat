import json
import os
from datetime import datetime, date
from typing import List, Dict, Any, Optional
from google.cloud import bigquery
from google.cloud.exceptions import NotFound
from base import WakalatLogger, alert_system_error


class BigQueryDocumentWriter:
    def __init__(self, project_id: str, dataset_id: str, table_id: str, credentials_path: str):
        """
        Initialize BigQuery writer for document storage.

        Args:
            project_id (str): GCP Project ID
            dataset_id (str): BigQuery dataset ID
            table_id (str): BigQuery table ID for document links
            credentials_path (str): Path to GCP credentials JSON file
        """
        self.logger = WakalatLogger("BigQueryDocumentWriter")
        self.project_id = project_id
        self.dataset_id = dataset_id
        self.table_id = table_id
        self.details_table_id = f"{table_id}_details"  # Separate table for document details
        self.parsed_table_id = f"{table_id}_parsed" # Separate table for parsed details

        # Initialize BigQuery client
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
        self.client = bigquery.Client(project=project_id)

        # Ensure tables exist
        self._ensure_tables_exist()

    def _ensure_tables_exist(self):
        """Create tables if they don't exist."""
        try:
            # Schema for document links table (existing)
            links_schema = [
                bigquery.SchemaField("doc_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("year", "INTEGER", mode="REQUIRED"),
                bigquery.SchemaField("metadata", "JSON", mode="NULLABLE"),
                bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
            ]

            # Schema for document details table (new)
            details_schema = [
                bigquery.SchemaField("doc_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("title", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("content", "STRING", mode="NULLABLE"),  # Main text content
                bigquery.SchemaField("raw_html", "STRING", mode="NULLABLE"),  # Raw HTML as blob
                bigquery.SchemaField("metadata", "JSON", mode="NULLABLE"),
                bigquery.SchemaField("url", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("content_length", "INTEGER", mode="NULLABLE"),
                bigquery.SchemaField("extracted_at", "TIMESTAMP", mode="REQUIRED"),
                bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
            ]

            # Schema for parsed document info
            parsed_schema = [
                bigquery.SchemaField("doc_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("parsed_at", "TIMESTAMP", mode="REQUIRED"),
                bigquery.SchemaField("success", "BOOLEAN", mode="REQUIRED"),
                bigquery.SchemaField("summary", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("key_arguments", "STRING", mode="REPEATED"),
                bigquery.SchemaField("legal_citations", "STRING", mode="REPEATED"),
                bigquery.SchemaField("parties_involved", "STRING", mode="REPEATED"),
                bigquery.SchemaField("legal_areas", "STRING", mode="REPEATED"),
                bigquery.SchemaField("judgment_type", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("court_name", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("judge_name", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("decision_date", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("case_number", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("outcome", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("case_details", "JSON", mode="NULLABLE"),
                bigquery.SchemaField("content_length", "INTEGER", mode="NULLABLE"),
                bigquery.SchemaField("processing_time_seconds", "FLOAT", mode="NULLABLE"),
                bigquery.SchemaField("error_message", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("ai_model_used", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("parsing_version", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("prompt_version", "STRING", mode="NULLABLE")
            ]

            self._create_table_if_not_exists(self.table_id, links_schema)
            self._create_table_if_not_exists(self.details_table_id, details_schema)
            self._create_table_if_not_exists(self.parsed_table_id, parsed_schema)

        except Exception as e:
            alert_system_error(
                component="bigquery_table_creation",
                error=e,
                context={
                    "project_id": self.project_id,
                    "dataset_id": self.dataset_id,
                    "table_id": self.table_id
                }
            )
            raise

    def _create_table_if_not_exists(self, table_id: str, schema: List[bigquery.SchemaField]):
        """Create a table if it doesn't exist."""
        table_ref = self.client.dataset(self.dataset_id).table(table_id)

        try:
            self.client.get_table(table_ref)
            self.logger.info(f"Table {table_id} already exists")
        except NotFound:
            table = bigquery.Table(table_ref, schema=schema)
            table = self.client.create_table(table)
            self.logger.info(f"Created table {table_id}")

    def insert_rows(self, rows: List[Dict[str, Any]], table_type: str = "links") -> bool:
        """
        Insert rows into BigQuery table.

        Args:
            rows (List[Dict]): List of row dictionaries to insert
            table_type (str): Either "links" or "details" to specify which table

        Returns:
            bool: True if successful, False otherwise
        """
        if not rows:
            self.logger.info("No rows to insert")
            return True

        try:
            # Choose the appropriate table
            target_table_id = None
            if table_type == "links":
                target_table_id = self.table_id
            elif table_type == "details":
                target_table_id = self.details_table_id
            elif table_type == "parses":
                target_table_id = self.parsed_table_id
            table_ref = self.client.dataset(self.dataset_id).table(target_table_id)
            table = self.client.get_table(table_ref)

            # Add timestamp to rows if not present
            current_time = datetime.now()
            if table_type != "parses":
                for row in rows:
                    if "created_at" not in row:
                        row["created_at"] = current_time.isoformat(sep=' ')
                    if 'year' in row and isinstance(row['year'], int):
                        year = row['year']
                        row['year'] = date(year, 1, 1).isoformat()
                    if 'metadata' in row and not isinstance(row['metadata'], str):
                        metadata = row['metadata']
                        row['metadata'] = json.dumps(metadata)

            # Insert rows
            errors = self.client.insert_rows_json(table, rows)

            if errors:
                self.logger.error(f"BigQuery insert errors: {errors}")
                alert_system_error(
                    component="bigquery_insert_rows",
                    error=Exception(f"Insert errors: {errors}"),
                    context={
                        "table_type": table_type,
                        "table_id": target_table_id,
                        "rows_count": len(rows),
                        "errors": errors
                    }
                )
                return False
            else:
                self.logger.info(f"Successfully inserted {len(rows)} rows into {target_table_id}")
                return True

        except Exception as e:
            self.logger.error(f"Error inserting rows into BigQuery: {e}")
            alert_system_error(
                component="bigquery_insert_rows",
                error=e,
                context={
                    "table_type": table_type,
                    "rows_count": len(rows)
                }
            )
            return False

    def insert_document_details(self, document_details: Dict[str, Any]) -> bool:
        """
        Insert document details into the details table.

        Args:
            document_details (Dict): Document details from fetch_document_details

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Prepare row for BigQuery
            row = {
                "doc_id": document_details["doc_id"],
                "title": document_details.get("title"),
                "content": document_details.get("content"),
                "raw_html": document_details.get("raw_html"),  # This is the blob
                "metadata": json.dumps(document_details.get("metadata", {})),
                "url": document_details.get("url"),
                "content_length": len(document_details.get("content", "")),
                "extracted_at": document_details["extracted_at"].isoformat(sep=' ') if isinstance(
                    document_details.get("extracted_at"), datetime) else datetime.now().isoformat(sep=' '),
            }

            return self.insert_rows([row], table_type="details")

        except Exception as e:
            self.logger.error(f"Error preparing document details for BigQuery: {e}")
            alert_system_error(
                component="document_details_preparation",
                error=e,
                context={
                    "doc_id": document_details.get("doc_id", "unknown")
                }
            )
            return False

    def insert_parsed_document_details(self, parsed_details: Dict[str, Any]) -> bool:
        """
        Insert parsed document details into the parsed table.

        Args:
            parsed_details (Dict): Parsed details dictionary

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Prepare row for BigQuery
            row = {
                "doc_id": parsed_details["doc_id"],
                "parsed_at": parsed_details.get("parsed_at").isoformat(sep=' ')
                             if isinstance(parsed_details.get("parsed_at"), datetime)
                             else datetime.now().isoformat(sep=' '),
                "success": parsed_details.get("success", False),
                "summary": parsed_details.get("summary"),
                "key_arguments": parsed_details.get("key_arguments", []),
                "legal_citations": parsed_details.get("legal_citations", []),
                "parties_involved": parsed_details.get("parties_involved", []),
                "legal_areas": parsed_details.get("legal_areas", []),
                "judgment_type": parsed_details.get("judgment_type"),
                "court_name": parsed_details.get("court_name"),
                "judge_name": parsed_details.get("judge_name"),
                "decision_date": parsed_details.get("decision_date"),
                "case_number": parsed_details.get("case_number"),
                "outcome": parsed_details.get("outcome"),
                "case_details": json.dumps(parsed_details.get("case_details", {})),
                "content_length": parsed_details.get("content_length"),
                "processing_time_seconds": parsed_details.get("processing_time_seconds"),
                "error_message": parsed_details.get("error_message"),
                "ai_model_used": parsed_details.get("ai_model_used"),
                "parsing_version": parsed_details.get("parsing_version"),
                "prompt_version": parsed_details.get("prompt_version"),
            }

            return self.insert_rows([row], table_type="parses")

        except Exception as e:
            self.logger.error(f"Error preparing parsed document details for BigQuery: {e}")
            alert_system_error(
                component="parsed_document_details_preparation",
                error=e,
                context={
                    "doc_id": parsed_details.get("doc_id", "unknown")
                }
            )
            return False


    def is_document_parsed(self, doc_id: str) -> bool:
        """
        Check if a document has already been parsed.

        Args:
            doc_id: Document ID to check

        Returns:
            True if document is already parsed
        """
        try:
            query = f"""
            SELECT COUNT(*) as count
            FROM `{self.project_id}.{self.dataset_id}.{self.parsed_table_id}`
            WHERE doc_id = @doc_id AND success = TRUE
            """

            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("doc_id", "STRING", doc_id)
                ]
            )

            query_job = self.client.query(query, job_config=job_config)
            results = list(query_job.result())

            return results[0].count > 0 if results else False

        except Exception as e:
            self.logger.warning(f"Error checking if document {doc_id} is parsed: {e}")
            return False


    def get_unparsed_documents(self, limit: int) -> List[int]:
        try:
            query = f"""
                        SELECT doc_id
                        FROM `{self.project_id}.{self.dataset_id}.{self.details_table_id}`
                        WHERE content IS NOT NULL
                        AND doc_id NOT IN (
                            SELECT doc_id
                            FROM `{self.project_id}.{self.dataset_id}.{self.parsed_table_id}`
                            WHERE success = TRUE
                        )
                        LIMIT {limit}
                        """

            query_job = self.client.query(query)
            return [row.doc_id for row in query_job.result()]

        except Exception as e:
            self.logger.error(f"Error getting unparsed documents: {e}")
            return []

    def check_document_exists(self, doc_id: str, table_type: str = "details") -> bool:
        """
        Check if a document already exists in the specified table.

        Args:
            doc_id (str): Document ID to check
            table_type (str): Either "links" or "details"

        Returns:
            bool: True if document exists, False otherwise
        """
        try:
            target_table_id = self.table_id if table_type == "links" else self.details_table_id
            query = f"""
                SELECT COUNT(*) as count
                FROM `{self.project_id}.{self.dataset_id}.{target_table_id}`
                WHERE doc_id = @doc_id
            """

            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("doc_id", "STRING", doc_id)
                ]
            )

            query_job = self.client.query(query, job_config=job_config)
            results = query_job.result()

            for row in results:
                return row.count > 0

            return False

        except Exception as e:
            self.logger.error(f"Error checking if document {doc_id} exists: {e}")
            return False

    def get_documents_without_details(self, limit: int = 100) -> List[str]:
        """
        Get document IDs that exist in links table but not in details table.

        Args:
            limit (int): Maximum number of document IDs to return

        Returns:
            List[str]: List of document IDs that need details fetched
        """
        try:
            query = f"""
                SELECT l.doc_id
                FROM `{self.project_id}.{self.dataset_id}.{self.table_id}` l
                LEFT JOIN `{self.project_id}.{self.dataset_id}.{self.details_table_id}` d
                ON l.doc_id = d.doc_id
                WHERE d.doc_id IS NULL
                LIMIT {limit}
            """

            query_job = self.client.query(query)
            results = query_job.result()

            return [row.doc_id for row in results]

        except Exception as e:
            self.logger.error(f"Error getting documents without details: {e}")
            alert_system_error(
                component="get_documents_without_details",
                error=e,
                context={
                    "limit": limit
                }
            )
            return []

    def get_table_stats(self) -> Dict[str, Any]:
        """
        Get statistics about both tables.

        Returns:
            Dict[str, Any]: Statistics about the tables
        """
        try:
            stats = {}

            # Links table stats
            links_query = f"""
                SELECT 
                    COUNT(*) as total_links,
                    COUNT(DISTINCT year) as years_covered,
                    MIN(year) as earliest_year,
                    MAX(year) as latest_year
                FROM `{self.project_id}.{self.dataset_id}.{self.table_id}`
            """

            # Details table stats
            details_query = f"""
                SELECT 
                    COUNT(*) as total_details,
                    AVG(content_length) as avg_content_length,
                    MAX(content_length) as max_content_length,
                    COUNT(CASE WHEN title IS NOT NULL THEN 1 END) as documents_with_titles
                FROM `{self.project_id}.{self.dataset_id}.{self.details_table_id}`
            """

            # Execute queries
            links_job = self.client.query(links_query)
            details_job = self.client.query(details_query)

            links_results = list(links_job.result())
            details_results = list(details_job.result())

            if links_results:
                stats["links"] = dict(links_results[0])

            if details_results:
                stats["details"] = dict(details_results[0])

            # Calculate completion percentage
            if stats.get("links", {}).get("total_links", 0) > 0:
                completion_rate = (stats.get("details", {}).get("total_details", 0) /
                                   stats["links"]["total_links"]) * 100
                stats["completion_percentage"] = round(completion_rate, 2)

            return stats

        except Exception as e:
            self.logger.error(f"Error getting table statistics: {e}")
            return {}