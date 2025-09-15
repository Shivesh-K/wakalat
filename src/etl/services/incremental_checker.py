"""
Incremental Document Checker

Compares newly retrieved documents with existing ones in BigQuery
to identify which documents need to be added.
"""

from typing import List, Dict, Set, Tuple, Optional, Any
from datetime import datetime, date, UTC
from google.cloud import bigquery

from base import WakalatLogger, alert_bigquery_failure, alert_data_validation_failure, alert_system_error
from src.data import DocRetriever
from ..models.etl_models import DocumentBatch, WatermarkState
from ..services.watermark_manager import WatermarkManager
from ... import DocRetrieverConstants


class IncrementalDocumentChecker:
    """
    Handles incremental document checking by comparing new documents
    with existing ones in BigQuery and identifying what needs to be added.
    """

    def __init__(self,
                 project_id: str,
                 dataset_id: str,
                 documents_table_id: str,
                 watermark_manager: WatermarkManager,
                 credentials_path: Optional[str] = None):
        """
        Initialize the incremental checker.

        Args:
            project_id: GCP project ID
            dataset_id: BigQuery dataset ID
            documents_table_id: Main documents table name
            watermark_manager: WatermarkManager instance
            credentials_path: Path to service account JSON (optional)
        """
        self.logger = WakalatLogger("IncrementalDocumentChecker")

        self.project_id = project_id
        self.dataset_id = dataset_id
        self.documents_table_id = documents_table_id
        self.watermark_manager = watermark_manager

        # Initialize BigQuery client
        if credentials_path:
            self.client = bigquery.Client.from_service_account_json(
                credentials_path, project=project_id
            )
        else:
            self.client = bigquery.Client(project=project_id)

        # Initialize document retriever
        self.doc_retriever = DocRetriever()

    def get_existing_document_ids(self, year: int) -> Set[str]:
        """
        Get all existing document IDs for a specific year from BigQuery.

        Args:
            year: Year to check

        Returns:
            Set of existing document IDs
        """
        year_date = date(year, 1, 1).isoformat()
        try:
            query = f"""
            SELECT DISTINCT doc_id
            FROM `{self.project_id}.{self.dataset_id}.{self.documents_table_id}`
            WHERE year = @year
            """

            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("year", "DATE", year_date)
                ]
            )

            query_job = self.client.query(query, job_config=job_config)
            results = list(query_job.result())

            existing_ids = {row.doc_id for row in results}
            self.logger.info(f"Found {len(existing_ids)} existing documents for year {year}")

            return existing_ids

        except Exception as e:
            self.logger.error(f"Error retrieving existing document IDs for year {year}: {e}")
            alert_bigquery_failure(
                operation="get_existing_document_ids",
                error=e,
                data_context={"year": year}
            )
            raise

    def retrieve_new_documents_for_year(self,
                                        year: int,
                                        start_page: int = 0,
                                        max_pages: Optional[int] = None) -> Tuple[List[DocumentBatch], int]:
        """
        Retrieve new documents for a specific year, starting from a given page.

        Args:
            year: Year to process
            start_page: Page to start from (based on watermark)
            max_pages: Maximum pages to process (None for unlimited)

        Returns:
            Tuple of (list of DocumentBatch objects, total_pages_processed)
        """
        try:
            # Get existing document IDs for this year
            existing_ids = self.get_existing_document_ids(year)

            batches = []
            page = start_page
            consecutive_empty_pages = 0
            max_consecutive_empty = 3
            total_pages_processed = 0

            self.logger.info(f"Starting document retrieval for year {year} from page {start_page}")

            while consecutive_empty_pages < max_consecutive_empty:
                if max_pages and total_pages_processed >= max_pages:
                    self.logger.info(f"Reached max pages limit ({max_pages}) for year {year}")
                    break

                try:
                    # Get documents with IDs for this page
                    documents_with_ids = self.doc_retriever.get_document_links_with_ids(year, page)

                    if not documents_with_ids:
                        consecutive_empty_pages += 1
                        self.logger.debug(f"Empty page {page} for year {year} "
                                          f"(consecutive: {consecutive_empty_pages})")
                        page += 1
                        total_pages_processed += 1
                        continue

                    # Reset consecutive empty counter
                    consecutive_empty_pages = 0

                    # Filter out documents that already exist
                    new_documents = []
                    for link, doc_id, doc_year in documents_with_ids:
                        if doc_id not in existing_ids:
                            new_documents.append({
                                "doc_id": doc_id,
                                "year": doc_year,
                                "blob_link": f"{DocRetrieverConstants.DOMAIN_NAME}{link}" if not link.startswith(
                                    'http') else link,
                                "metadata": {
                                    "page": page,
                                    "original_link": link,
                                    "retrieved_at": datetime.now(UTC).isoformat()
                                }
                            })
                            # Add to existing_ids to avoid duplicates within this run
                            existing_ids.add(doc_id)

                    if new_documents:
                        batch = DocumentBatch(
                            year=year,
                            page=page,
                            documents=new_documents
                        )
                        batches.append(batch)

                        self.logger.info(f"Year {year}, Page {page}: Found {len(new_documents)} new documents "
                                         f"(out of {len(documents_with_ids)} total)")
                    else:
                        self.logger.debug(f"Year {year}, Page {page}: No new documents "
                                          f"(all {len(documents_with_ids)} already exist)")

                    page += 1
                    total_pages_processed += 1

                    # Add small delay to be respectful to the source server
                    import time
                    time.sleep(0.5)

                except Exception as e:
                    self.logger.error(f"Error processing year {year}, page {page}: {e}")
                    consecutive_empty_pages += 1
                    page += 1
                    total_pages_processed += 1

                    if consecutive_empty_pages >= max_consecutive_empty:
                        break

            total_new_documents = sum(len(batch) for batch in batches)
            self.logger.info(f"Year {year} retrieval complete: {total_new_documents} new documents "
                             f"across {len(batches)} batches, {total_pages_processed} pages processed")

            return batches, total_pages_processed

        except Exception as e:
            alert_system_error(
                component="retrieve_new_documents_for_year",
                error=e,
                context={
                    "year": year,
                    "start_page": start_page,
                    "max_pages": max_pages
                }
            )
            raise

    def validate_document_batch(self, batch: DocumentBatch) -> List[str]:
        """
        Validate a document batch for required fields and data integrity.

        Args:
            batch: DocumentBatch to validate

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        try:
            if batch.is_empty():
                return errors  # Empty batches are valid

            for i, doc in enumerate(batch.documents):
                # Required field validation
                if 'doc_id' not in doc or not doc['doc_id']:
                    errors.append(f"Document {i}: doc_id is required")

                if 'year' not in doc or not doc['year']:
                    errors.append(f"Document {i}: year is required")

                # Data type validation
                if 'doc_id' in doc and not isinstance(doc['doc_id'], str):
                    errors.append(f"Document {i}: doc_id must be string, got {type(doc['doc_id'])}")

                if 'year' in doc and not isinstance(doc['year'], int):
                    errors.append(f"Document {i}: year must be integer, got {type(doc['year'])}")

                # Year consistency check
                if 'year' in doc and doc['year'] != batch.year:
                    errors.append(f"Document {i}: year mismatch - batch={batch.year}, doc={doc['year']}")

                # URL validation for blob_link
                if 'blob_link' in doc and doc['blob_link']:
                    blob_link = doc['blob_link']
                    if not (blob_link.startswith('http://') or blob_link.startswith('https://')):
                        errors.append(f"Document {i}: blob_link must be valid URL")

            if errors:
                alert_data_validation_failure(
                    validation_errors=errors,
                    data_sample={
                        "batch_year": batch.year,
                        "batch_page": batch.page,
                        "document_count": len(batch.documents),
                        "sample_document": batch.documents[0] if batch.documents else None
                    }
                )

            return errors

        except Exception as e:
            alert_system_error(
                component="validate_document_batch",
                error=e,
                context={
                    "batch_year": batch.year,
                    "batch_page": batch.page,
                    "document_count": len(batch.documents)
                }
            )
            return [f"Validation error: {str(e)}"]

    def check_incremental_updates(self,
                                  years: List[int],
                                  max_pages_per_year: Optional[int] = 50) -> Dict[int, List[DocumentBatch]]:
        """
        Check for incremental updates across multiple years.

        Args:
            years: List of years to check
            max_pages_per_year: Maximum pages to process per year

        Returns:
            Dictionary mapping year to list of DocumentBatch objects with new documents
        """
        results = {}

        for year in years:
            try:
                # Get current watermark for this year
                watermark = self.watermark_manager.get_watermark(year)
                start_page = 0

                self.logger.info(f"Checking year {year} starting from page {start_page}")

                # Retrieve new documents for this year
                batches, pages_processed = self.retrieve_new_documents_for_year(
                    year=year,
                    start_page=start_page,
                    max_pages=40
                )

                # Validate all batches
                valid_batches = []
                for batch in batches:
                    validation_errors = self.validate_document_batch(batch)
                    if not validation_errors:
                        valid_batches.append(batch)
                    else:
                        self.logger.error(f"Batch validation failed for year {year}, page {batch.page}: "
                                          f"{len(validation_errors)} errors")

                results[year] = valid_batches

                # Update watermark if we processed any pages
                if pages_processed > 0:
                    new_watermark = WatermarkState(
                        year=year,
                        last_processed_page=start_page + pages_processed - 1,
                        last_document_id=None,  # Could enhance to track last doc ID
                        last_updated=datetime.now(UTC),
                        total_documents=(watermark.total_documents if watermark else 0) +
                                        sum(len(batch) for batch in valid_batches),
                        is_complete=(pages_processed < max_pages_per_year) if max_pages_per_year else False
                    )

                    self.watermark_manager.update_watermark(new_watermark)

                total_new_docs = sum(len(batch) for batch in valid_batches)

                self.logger.info(f"Year {year}: {total_new_docs} new documents found")

            except Exception as e:
                self.logger.error(f"Error checking year {year}: {e}")
                results[year] = []  # Continue with other years

        return results

    def get_processing_summary(self, results: Dict[int, List[DocumentBatch]]) -> Dict[str, Any]:
        """
        Generate a summary of the incremental processing results.

        Args:
            results: Results from check_incremental_updates

        Returns:
            Dictionary with processing summary
        """
        total_new_documents = 0
        years_with_updates = 0
        year_summaries = {}

        for year, batches in results.items():
            year_total = sum(len(batch) for batch in batches)
            total_new_documents += year_total

            if year_total > 0:
                years_with_updates += 1

            year_summaries[year] = {
                "new_documents": year_total,
                "batches": len(batches),
                "pages_with_data": len([b for b in batches if not b.is_empty()])
            }

        return {
            "total_new_documents": total_new_documents,
            "years_processed": len(results),
            "years_with_updates": years_with_updates,
            "year_summaries": year_summaries,
            "processed_at": datetime.now(UTC).isoformat()
        }