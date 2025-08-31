"""
Comprehensive Document Retriever with Document Details Fetching

This module retrieves all documents from the starting year to end year,
and can fetch detailed content for specific document IDs.
"""

import json
import os
import time
from datetime import datetime
from typing import List, Tuple, Optional, Dict, Any

from dotenv import load_dotenv

from base import WakalatLogger, alert_system_error
from .doc_id_retriever import DocRetriever
from .constants import DocRetrieverConstants
from .bigquery_document_writer import BigQueryDocumentWriter

load_dotenv()


class ComprehensiveDocRetriever:
    def __init__(self, delay_between_requests: float = 1.0):
        """Initialize comprehensive document retriever with alerting."""
        self.logger = WakalatLogger("ComprehensiveDocRetriever")
        self.doc_retriever = DocRetriever()
        self.delay_between_requests = delay_between_requests

        try:
            self.bq_doc_writer = BigQueryDocumentWriter(
                project_id=os.getenv('GCP.PROJECT_ID'),
                dataset_id=os.getenv('GCP.DATASET_ID'),
                table_id=os.getenv('GCP.TABLE_ID'),
                credentials_path=os.getenv('GCP.CREDENTIALS_PATH')
            )
        except Exception as e:
            alert_system_error(
                component="BigQueryDocumentWriter_initialization",
                error=e,
                context={
                    "project_id": os.getenv('GCP.PROJECT_ID'),
                    "dataset_id": os.getenv('GCP.DATASET_ID'),
                    "table_id": os.getenv('GCP.TABLE_ID')
                }
            )
            raise

    def retrieve_all_documents(self,
                               start_year: Optional[int] = None,
                               end_year: Optional[int] = None,
                               save_to_file: bool = True,
                               save_to_bq: bool = True,
                               output_filename: Optional[str] = None) -> List[Tuple[str, str, int]]:
        """
        Retrieve all documents from start year to end year across all pages.

        Args:
            start_year (int, optional): Starting year (uses constant if not provided)
            end_year (int, optional): Ending year (uses constant if not provided)
            save_to_file (bool): Whether to save results to JSON file
            save_to_bq (bool): Whether to save results to BigQuery
            output_filename (str, optional): Output filename (auto-generated if not provided)

        Returns:
            List[Tuple[str, str, int]]: List of (link, document_id, year) tuples as value
        """
        # Use default year range from constants if not provided
        if start_year is None or end_year is None:
            year_range = DocRetrieverConstants.get_year_range()
            start_year = min(year_range) if start_year is None else start_year
            end_year = max(year_range) if end_year is None else end_year

        self.logger.info(f"Starting comprehensive document retrieval from {start_year} to {end_year}")

        all_results = []
        total_documents = 0
        start_time = datetime.now()

        # Process each year
        for year in range(end_year, start_year - 1, -1):
            self.logger.info(f"Processing year: {year}")
            year_documents = self._retrieve_documents_for_year(year)
            all_results.extend(year_documents)
            total_documents += len(year_documents)

            self.logger.info(f"Year {year} completed: {len(year_documents)} documents found")

            # Small delay between years to be respectful to the server
            if year < end_year:
                time.sleep(self.delay_between_requests)

        end_time = datetime.now()
        duration = end_time - start_time

        self.logger.info(f"Comprehensive retrieval completed!")
        self.logger.info(f"Total documents retrieved: {total_documents}")
        self.logger.info(f"Total time taken: {duration}")
        self.logger.info(f"Years processed: {start_year}-{end_year}")

        # Save to file if requested
        if save_to_file:
            if output_filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_filename = f"comprehensive_documents_{start_year}_{end_year}_{timestamp}.json"

            self._save_results_to_file(all_results, output_filename, total_documents, duration)

        if save_to_bq:
            self.bq_doc_writer.insert_rows([
                {
                    "doc_id": result[1],
                    "year": result[2],
                    "metadata": {
                        "link": result[0]
                    }
                } for result in all_results
            ])

        return all_results

    def fetch_document_details(self, doc_id: str, save_to_bq: bool = True) -> Optional[Dict[str, Any]]:
        """
        Fetch detailed content for a specific document ID.

        Args:
            doc_id (str): Document ID to fetch details for
            save_to_bq (bool): Whether to save to BigQuery

        Returns:
            Dict[str, Any]: Document details or None if failed
        """
        self.logger.info(f"Fetching details for document ID: {doc_id}")

        try:
            # Check if document details already exist
            if save_to_bq and self.bq_doc_writer.check_document_exists(doc_id, "details"):
                self.logger.info(f"Document {doc_id} details already exist in BigQuery")
                return None

            # Fetch document details
            document_details = self.doc_retriever.fetch_document_details(doc_id)

            if not document_details:
                self.logger.warning(f"Failed to fetch details for document {doc_id}")
                return None

            # Save to BigQuery if requested
            if save_to_bq:
                success = self.bq_doc_writer.insert_document_details(document_details)
                if success:
                    self.logger.info(f"Document {doc_id} details saved to BigQuery")
                else:
                    self.logger.error(f"Failed to save document {doc_id} details to BigQuery")

            return document_details

        except Exception as e:
            self.logger.error(f"Error fetching document details for {doc_id}: {e}")
            alert_system_error(
                component="fetch_document_details",
                error=e,
                context={
                    "doc_id": doc_id
                }
            )
            return None

    def fetch_missing_document_details(self,
                                       batch_size: int = 10,
                                       max_documents: Optional[int] = None) -> Dict[str, Any]:
        """
        Fetch details for documents that exist in links table but not in details table.

        Args:
            batch_size (int): Number of documents to process in one batch
            max_documents (int, optional): Maximum number of documents to process

        Returns:
            Dict[str, Any]: Summary of the operation
        """
        self.logger.info("Starting fetch of missing document details")
        start_time = datetime.now()

        # Get documents without details
        missing_doc_ids = self.bq_doc_writer.get_documents_without_details(
            limit=max_documents or 1000
        )

        if not missing_doc_ids:
            self.logger.info("No missing document details found")
            return {
                "total_processed": 0,
                "successful": 0,
                "failed": 0,
                "duration": str(datetime.now() - start_time)
            }

        self.logger.info(f"Found {len(missing_doc_ids)} documents without details")

        # Limit to max_documents if specified
        if max_documents:
            missing_doc_ids = missing_doc_ids[:max_documents]
            self.logger.info(f"Limited to {len(missing_doc_ids)} documents")

        successful_fetches = 0
        failed_fetches = 0

        # Process documents in batches
        for i in range(0, len(missing_doc_ids), batch_size):
            batch = missing_doc_ids[i:i + batch_size]
            self.logger.info(f"Processing batch {i//batch_size + 1}: documents {i+1}-{min(i+batch_size, len(missing_doc_ids))}")

            for doc_id in batch:
                try:
                    result = self.fetch_document_details(doc_id, save_to_bq=True)
                    if result:
                        successful_fetches += 1
                        self.logger.debug(f"Successfully fetched details for {doc_id}")
                    else:
                        failed_fetches += 1
                        self.logger.warning(f"Failed to fetch details for {doc_id}")

                    # Delay between requests
                    time.sleep(self.delay_between_requests)

                except Exception as e:
                    failed_fetches += 1
                    self.logger.error(f"Exception fetching details for {doc_id}: {e}")

            # Longer delay between batches
            if i + batch_size < len(missing_doc_ids):
                self.logger.info(f"Batch completed. Waiting {self.delay_between_requests * 2}s before next batch...")
                time.sleep(self.delay_between_requests * 2)

        end_time = datetime.now()
        duration = end_time - start_time

        summary = {
            "total_processed": len(missing_doc_ids),
            "successful": successful_fetches,
            "failed": failed_fetches,
            "success_rate": (successful_fetches / len(missing_doc_ids)) * 100 if missing_doc_ids else 0,
            "duration": str(duration),
            "duration_seconds": duration.total_seconds()
        }

        self.logger.info("Missing document details fetch completed!")
        self.logger.info(f"Total processed: {summary['total_processed']}")
        self.logger.info(f"Successful: {summary['successful']}")
        self.logger.info(f"Failed: {summary['failed']}")
        self.logger.info(f"Success rate: {summary['success_rate']:.2f}%")
        self.logger.info(f"Duration: {summary['duration']}")

        return summary

    def _retrieve_documents_for_year(self, year: int) -> List[Tuple[str, str, int]]:
        """Retrieve all documents for a specific year with enhanced error handling."""
        all_documents = []
        page = 0
        consecutive_empty_pages = 0
        max_consecutive_empty_pages = 3
        consecutive_errors = 0
        max_consecutive_errors = 5

        self.logger.info(f"Starting page iteration for year {year}")

        while consecutive_empty_pages < max_consecutive_empty_pages:
            self.logger.debug(f"Processing year {year}, page {page}")

            try:
                documents_with_ids = self.doc_retriever.get_document_links_with_ids(year, page)

                if not documents_with_ids:
                    consecutive_empty_pages += 1
                    consecutive_errors = 0  # Reset error count on successful (empty) response

                    self.logger.debug(f"No documents found for year {year}, page {page}. "
                                      f"Consecutive empty pages: {consecutive_empty_pages}")

                    if consecutive_empty_pages >= max_consecutive_empty_pages:
                        self.logger.info(f"Stopping year {year} after {consecutive_empty_pages} "
                                         f"consecutive empty pages. Last page: {page}")
                        break
                else:
                    consecutive_empty_pages = 0
                    consecutive_errors = 0
                    all_documents.extend(documents_with_ids)
                    self.logger.info(f"Year {year}, Page {page}: Found {len(documents_with_ids)} documents")

                page += 1
                time.sleep(self.delay_between_requests)

            except Exception as e:
                consecutive_errors += 1
                self.logger.error(f"Error processing year {year}, page {page}: {e}")

                # Alert if we're seeing too many consecutive errors
                if consecutive_errors >= max_consecutive_errors:
                    alert_system_error(
                        component="document_retrieval_loop",
                        error=e,
                        context={
                            "year": year,
                            "page": page,
                            "consecutive_errors": consecutive_errors,
                            "documents_found_so_far": len(all_documents)
                        }
                    )
                    break

                consecutive_empty_pages += 1

                if consecutive_empty_pages >= max_consecutive_empty_pages:
                    break

                page += 1
                time.sleep(self.delay_between_requests * 2)  # Longer delay after error

        self.logger.info(f"Year {year} completed: {len(all_documents)} total documents, "
                         f"last page processed: {page - 1}")
        return all_documents

    def _save_results_to_file(self,
                              results: List[Tuple[str, str, int]],
                              filename: str,
                              total_documents: int,
                              duration) -> None:
        """
        Save results to JSON file with metadata.

        Args:
            results: Results list
            filename: Output filename
            total_documents: Total number of documents retrieved
            duration: Time taken for retrieval
        """
        try:
            # Prepare data for JSON serialization
            json_data = {
                "metadata": {
                    "total_documents": total_documents,
                    "duration_seconds": duration.total_seconds(),
                    "duration_human": str(duration),
                    "generated_at": datetime.now().isoformat(),
                },
                "data": [
                    {"link": link, "document_id": doc_id, "year": year}
                    for link, doc_id, year in results
                ]
            }

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)

            self.logger.info(f"Results saved to: {filename}")

        except Exception as e:
            self.logger.error(f"Error saving results to file: {e}")

    def get_system_status(self) -> Dict[str, Any]:
        """
        Get comprehensive system status including table statistics.

        Returns:
            Dict[str, Any]: System status information
        """
        try:
            stats = self.bq_doc_writer.get_table_stats()

            status = {
                "timestamp": datetime.now().isoformat(),
                "bigquery_stats": stats,
                "configuration": {
                    "project_id": os.getenv('GCP.PROJECT_ID'),
                    "dataset_id": os.getenv('GCP.DATASET_ID'),
                    "table_id": os.getenv('GCP.TABLE_ID'),
                    "delay_between_requests": self.delay_between_requests,
                    "year_range": f"{DocRetrieverConstants.START_YEAR}-{DocRetrieverConstants.END_YEAR}"
                }
            }

            return status

        except Exception as e:
            self.logger.error(f"Error getting system status: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }


def main():
    """Main function to demonstrate comprehensive document retrieval with details fetching."""
    # Initialize the comprehensive retriever
    retriever = ComprehensiveDocRetriever(delay_between_requests=0.5)

    # Example workflows:

    # 1. Retrieve document links (existing functionality)
    print("=== Option 1: Retrieve Document Links ===")
    """
    results = retriever.retrieve_all_documents(
        start_year=2023,
        end_year=2024,
        save_to_file=True,
        save_to_bq=True
    )
    """

    # 2. Fetch details for a specific document
    print("=== Option 2: Fetch Specific Document Details ===")
    """
    doc_id = "12345678"  # Replace with actual document ID
    details = retriever.fetch_document_details(doc_id, save_to_bq=True)
    if details:
        print(f"Successfully fetched details for document {doc_id}")
        print(f"Title: {details.get('title', 'N/A')}")
        print(f"Content length: {len(details.get('content', ''))}")
    """

    # 3. Fetch details for all missing documents
    print("=== Option 3: Fetch Missing Document Details ===")
    """
    summary = retriever.fetch_missing_document_details(
        batch_size=5,      # Process 5 documents at a time
        max_documents=50   # Limit to 50 documents for testing
    )
    print("Fetch Summary:")
    print(f"Total processed: {summary['total_processed']}")
    print(f"Successful: {summary['successful']}")
    print(f"Failed: {summary['failed']}")
    print(f"Success rate: {summary['success_rate']:.2f}%")
    """

    # 4. Get system status
    print("=== System Status ===")
    status = retriever.get_system_status()
    print("BigQuery Statistics:")
    if "bigquery_stats" in status:
        stats = status["bigquery_stats"]
        if "links" in stats:
            print(f"  Links table: {stats['links'].get('total_links', 0)} documents")
            print(f"  Years covered: {stats['links'].get('years_covered', 0)}")
        if "details" in stats:
            print(f"  Details table: {stats['details'].get('total_details', 0)} documents")
            print(f"  Avg content length: {stats['details'].get('avg_content_length', 0):.0f} chars")
        if "completion_percentage" in stats:
            print(f"  Completion rate: {stats['completion_percentage']}%")


if __name__ == '__main__':
    main()