from google.cloud import bigquery
from google.cloud.exceptions import NotFound
from typing import List, Dict, Any, Optional
import json
from datetime import datetime, date
from base import WakalatLogger, alert_bigquery_failure, alert_data_validation_failure


class BigQueryDocumentWriter:
    """
    A class to handle writing document data to a BigQuery table.

    Table Schema:
    - doc_id: STRING (REQUIRED) - ID of the document
    - year: DATE (NULLABLE) - Date that the document was created
    - blob_link: STRING (NULLABLE) - Link to blob of document
    - metadata: JSON (NULLABLE) - Extra metadata such as page number, etc.
    - id: STRING (NULLABLE) - Primary key
    - created_at: TIMESTAMP (NULLABLE) - Creation timestamp
    - updated_at: TIMESTAMP (NULLABLE) - Update timestamp
    """

    def __init__(self, project_id: str, dataset_id: str, table_id: str,
                 credentials_path: Optional[str] = None):
        """
        Initialize the BigQuery writer.

        Args:
            project_id: Google Cloud Project ID
            dataset_id: BigQuery Dataset ID
            table_id: BigQuery Table ID
            credentials_path: Path to service account JSON file (optional)
        """

        # Configure logging
        self.logger = WakalatLogger(__name__)

        self.project_id = project_id
        self.dataset_id = dataset_id
        self.table_id = table_id

        # Initialize BigQuery client
        if credentials_path:
            self.client = bigquery.Client.from_service_account_json(
                credentials_path, project=project_id
            )
        else:
            # Use default credentials (e.g., from environment)
            self.client = bigquery.Client(project=project_id)

        # Set up table reference
        self.table_ref = self.client.dataset(dataset_id).table(table_id)

        # Verify table exists
        self._verify_table_exists()

    def _verify_table_exists(self) -> bool:
        """Verify that the target table exists."""
        try:
            self.client.get_table(self.table_ref)
            self.logger.info(f"Table {self.project_id}.{self.dataset_id}.{self.table_id} found")
            return True
        except NotFound as e:
            alert_bigquery_failure(
                operation="table_verification",
                error=e,
                data_context={
                    "project_id": self.project_id,
                    "dataset_id": self.dataset_id,
                    "table_id": self.table_id
                }
            )
            raise

    def _serialize_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively serialize metadata, converting datetime objects to strings.

        Args:
            metadata: Dictionary that may contain datetime objects

        Returns:
            Dictionary with datetime objects converted to ISO format strings
        """
        if not isinstance(metadata, dict):
            return metadata

        serialized = {}
        for key, value in metadata.items():
            if isinstance(value, (datetime, date)):
                serialized[key] = value.isoformat()
            elif isinstance(value, dict):
                serialized[key] = self._serialize_metadata(value)
            elif isinstance(value, list):
                serialized[key] = [
                    item.isoformat() if isinstance(item, (datetime, date))
                    else self._serialize_metadata(item) if isinstance(item, dict)
                    else item
                    for item in value
                ]
            else:
                serialized[key] = value
        return serialized

    def _validate_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and clean a row before insertion.

        Args:
            row: Dictionary containing row data

        Returns:
            Cleaned and validated row dictionary
        """
        try:
            cleaned_row = {}

            # Required field validation
            if 'doc_id' not in row or not row['doc_id']:
                raise ValueError("doc_id is required and cannot be empty")

            cleaned_row['doc_id'] = str(row['doc_id'])

            # Handle optional fields
            if 'year' in row and row['year'] is not None:
                if isinstance(row['year'], int):
                    cleaned_row['year'] = date(year=row['year'], month=1, day=1)
                else:
                    raise ValueError(f"year must be a date, datetime, or date string, got: {type(row['year'])}")

            if 'blob_link' in row and row['blob_link'] is not None:
                cleaned_row['blob_link'] = str(row['blob_link'])

            if 'metadata' in row and row['metadata'] is not None:
                if isinstance(row['metadata'], dict):
                    # Serialize any datetime objects in metadata
                    cleaned_row['metadata'] = json.dumps(self._serialize_metadata(row['metadata']))
                elif isinstance(row['metadata'], str):
                    try:
                        parsed_metadata = json.loads(row['metadata'])
                        cleaned_row['metadata'] = json.dumps(self._serialize_metadata(parsed_metadata))
                    except json.JSONDecodeError:
                        raise ValueError(f"metadata string is not valid JSON: {row['metadata']}")
                else:
                    raise ValueError(f"metadata must be a dict or JSON string, got: {type(row['metadata'])}")

            if 'id' in row and row['id'] is not None:
                cleaned_row['id'] = str(row['id'])

            # Handle timestamps - auto-set if not provided
            current_time = datetime.utcnow()

            if 'created_at' in row and row['created_at'] is not None:
                if isinstance(row['created_at'], str):
                    try:
                        cleaned_row['created_at'] = datetime.fromisoformat(row['created_at'].replace('Z', '+00:00'))
                    except ValueError:
                        raise ValueError(f"created_at must be in ISO format, got: {row['created_at']}")
                elif isinstance(row['created_at'], datetime):
                    cleaned_row['created_at'] = row['created_at']
                else:
                    raise ValueError(f"created_at must be a datetime or ISO string, got: {type(row['created_at'])}")
            else:
                cleaned_row['created_at'] = current_time

            if 'updated_at' in row and row['updated_at'] is not None:
                if isinstance(row['updated_at'], str):
                    try:
                        cleaned_row['updated_at'] = datetime.fromisoformat(row['updated_at'].replace('Z', '+00:00'))
                    except ValueError:
                        raise ValueError(f"updated_at must be in ISO format, got: {row['updated_at']}")
                elif isinstance(row['updated_at'], datetime):
                    cleaned_row['updated_at'] = row['updated_at']
                else:
                    raise ValueError(f"updated_at must be a datetime or ISO string, got: {type(row['updated_at'])}")
            else:
                cleaned_row['updated_at'] = current_time

            return cleaned_row
        except ValueError as e:
            # Collect validation errors for alerting
            alert_data_validation_failure(
                validation_errors=[str(e)],
                data_sample=row,
                context={"validation_step": "row_cleaning"}
            )
            raise

    def insert_row(self, row: Dict[str, Any]) -> bool:
        """
        Insert a single row into the table.

        Args:
            row: Dictionary containing row data

        Returns:
            True if successful, raises exception if failed
        """
        try:
            cleaned_row = self._validate_row(row)

            errors = self.client.insert_rows_json(
                self.table_ref, [cleaned_row]
            )

            if errors:
                self.logger.error(f"Failed to insert row: {errors}")
                raise RuntimeError(f"BigQuery insert errors: {errors}")

            self.logger.info(f"Successfully inserted row with doc_id: {cleaned_row['doc_id']}")
            return True

        except Exception as e:
            self.logger.error(f"Error inserting row: {str(e)}")
            # Alert for unexpected errors
            if not isinstance(e, RuntimeError):
                alert_bigquery_failure(
                    operation="insert_row",
                    error=e,
                    data_context={"row_data": row}
                )
            raise

    def insert_rows(self, rows: List[Dict[str, Any]], chunk_size: int = 1000) -> bool:
        """
        Insert multiple rows into the table.

        Args:
            rows: List of dictionaries containing row data
            chunk_size: Number of rows to insert per batch

        Returns:
            True if all successful, raises exception if any failed
        """
        if not rows:
            self.logger.warning("No rows to insert")
            return True

        try:
            # Process rows in chunks
            total_rows = len(rows)
            successful_inserts = 0

            for i in range(0, total_rows, chunk_size):
                chunk = rows[i:i + chunk_size]
                cleaned_chunk = []

                # Validate each row in the chunk
                for j, row in enumerate(chunk):
                    try:
                        cleaned_row = self._validate_row(row)
                        for key, value in cleaned_row.items():
                            if isinstance(value, date):
                                cleaned_row[key] = value.isoformat()
                            elif isinstance(value, datetime):
                                cleaned_row[key] = value.isoformat(sep=' ')
                        cleaned_chunk.append(cleaned_row)
                    except Exception as e:
                        self.logger.error(f"Validation error in row {i + j}: {str(e)}")
                        raise ValueError(f"Row {i + j} validation failed: {str(e)}")

                # Insert the chunk
                if cleaned_chunk:
                    errors = self.client.insert_rows_json(
                        self.table_ref, cleaned_chunk
                    )

                    if errors:
                        self.logger.error(f"Failed to insert chunk {i // chunk_size + 1}: {errors}")
                        raise RuntimeError(f"BigQuery insert errors in chunk {i // chunk_size + 1}: {errors}")

                    successful_inserts += len(cleaned_chunk)
                    self.logger.info(f"Successfully inserted chunk {i // chunk_size + 1} ({len(cleaned_chunk)} rows)")

            self.logger.info(f"Successfully inserted all {successful_inserts} rows")
            return True

        except Exception as e:
            self.logger.error(f"Error inserting rows: {str(e)}")
            if not isinstance(e, (RuntimeError, ValueError)):
                alert_bigquery_failure(
                    operation="insert_rows",
                    error=e,
                    data_context={
                        "total_rows": len(rows),
                        "chunk_size": chunk_size
                    }
                )
            raise
