"""
Comprehensive Document Retriever

This module retrieves all documents from the starting year to end year,
going through all pages until no more documents are found for each year.
"""

import json
import time
from datetime import datetime
from typing import Dict, List, Tuple, Optional

from base import WakalatLogger
from doc_id_retriever import DocRetriever
from constants import DocRetrieverConstants


class ComprehensiveDocRetriever:
    def __init__(self, delay_between_requests: float = 1.0):
        """
        Initialize comprehensive document retriever.

        Args:
            delay_between_requests (float): Delay in seconds between HTTP requests
        """
        self.logger = WakalatLogger("ComprehensiveDocRetriever")
        self.doc_retriever = DocRetriever()
        self.delay_between_requests = delay_between_requests

    def retrieve_all_documents(self,
                               start_year: Optional[int] = None,
                               end_year: Optional[int] = None,
                               save_to_file: bool = True,
                               output_filename: Optional[str] = None) -> Dict[int, List[Tuple[str, str]]]:
        """
        Retrieve all documents from start year to end year across all pages.

        Args:
            start_year (int, optional): Starting year (uses constant if not provided)
            end_year (int, optional): Ending year (uses constant if not provided)
            save_to_file (bool): Whether to save results to JSON file
            output_filename (str, optional): Output filename (auto-generated if not provided)

        Returns:
            Dict[int, List[Tuple[str, str]]]: Dictionary with year as key and
                                            list of (link, document_id) tuples as value
        """
        # Use default year range from constants if not provided
        if start_year is None or end_year is None:
            year_range = DocRetrieverConstants.get_year_range()
            start_year = min(year_range) if start_year is None else start_year
            end_year = max(year_range) if end_year is None else end_year

        self.logger.info(f"Starting comprehensive document retrieval from {start_year} to {end_year}")

        all_results = {}
        total_documents = 0
        start_time = datetime.now()

        # Process each year
        for year in range(start_year, end_year + 1):
            self.logger.info(f"Processing year: {year}")
            year_documents = self._retrieve_documents_for_year(year)
            all_results[year] = year_documents
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

        return all_results

    def _retrieve_documents_for_year(self, year: int) -> List[Tuple[str, str]]:
        """
        Retrieve all documents for a specific year by going through all pages.

        Args:
            year (int): Year to process

        Returns:
            List[Tuple[str, str]]: List of (link, document_id) tuples
        """
        all_documents = []
        page = 0  # Starting from page 0
        consecutive_empty_pages = 0
        max_consecutive_empty_pages = 3  # Stop after 3 consecutive empty pages

        self.logger.info(f"Starting page iteration for year {year}")

        while consecutive_empty_pages < max_consecutive_empty_pages:
            self.logger.debug(f"Processing year {year}, page {page}")

            try:
                # Get documents for current page
                documents_with_ids = self.doc_retriever.get_document_links_with_ids(year, page)

                if not documents_with_ids:
                    consecutive_empty_pages += 1
                    self.logger.debug(f"No documents found for year {year}, page {page}. "
                                      f"Consecutive empty pages: {consecutive_empty_pages}")

                    if consecutive_empty_pages >= max_consecutive_empty_pages:
                        self.logger.info(f"Stopping year {year} after {consecutive_empty_pages} "
                                         f"consecutive empty pages. Last page: {page}")
                        break
                else:
                    # Reset consecutive empty pages counter
                    consecutive_empty_pages = 0
                    all_documents.extend(documents_with_ids)
                    self.logger.info(f"Year {year}, Page {page}: Found {len(documents_with_ids)} documents")

                page += 1

                # Add delay between requests to be respectful to the server
                time.sleep(self.delay_between_requests)

            except Exception as e:
                self.logger.error(f"Error processing year {year}, page {page}: {e}")
                consecutive_empty_pages += 1

                # If we hit too many errors, break
                if consecutive_empty_pages >= max_consecutive_empty_pages:
                    break

                page += 1
                time.sleep(self.delay_between_requests * 2)  # Longer delay after error

        self.logger.info(f"Year {year} completed: {len(all_documents)} total documents, "
                         f"last page processed: {page - 1}")
        return all_documents

    def _save_results_to_file(self,
                              results: Dict[int, List[Tuple[str, str]]],
                              filename: str,
                              total_documents: int,
                              duration) -> None:
        """
        Save results to JSON file with metadata.

        Args:
            results: Results dictionary
            filename: Output filename
            total_documents: Total number of documents retrieved
            duration: Time taken for retrieval
        """
        try:
            # Prepare data for JSON serialization
            json_data = {
                "metadata": {
                    "total_documents": total_documents,
                    "total_years": len(results),
                    "duration_seconds": duration.total_seconds(),
                    "duration_human": str(duration),
                    "generated_at": datetime.now().isoformat(),
                    "years_processed": list(results.keys())
                },
                "data": {}
            }

            # Convert tuples to dictionaries for better JSON structure
            for year, documents in results.items():
                json_data["data"][str(year)] = [
                    {"link": link, "document_id": doc_id}
                    for link, doc_id in documents
                ]

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)

            self.logger.info(f"Results saved to: {filename}")

        except Exception as e:
            self.logger.error(f"Error saving results to file: {e}")

    def get_summary_statistics(self, results: Dict[int, List[Tuple[str, str]]]) -> Dict:
        """
        Generate summary statistics from results.

        Args:
            results: Results dictionary

        Returns:
            Dict: Summary statistics
        """
        stats = {
            "total_years": len(results),
            "total_documents": sum(len(docs) for docs in results.values()),
            "documents_per_year": {year: len(docs) for year, docs in results.items()},
            "years_with_no_documents": [year for year, docs in results.items() if len(docs) == 0],
            "most_productive_year": None,
            "least_productive_year": None
        }

        if results:
            # Find most and least productive years
            year_counts = [(year, len(docs)) for year, docs in results.items()]
            year_counts.sort(key=lambda x: x[1], reverse=True)

            if year_counts:
                stats["most_productive_year"] = {"year": year_counts[0][0], "count": year_counts[0][1]}
                stats["least_productive_year"] = {"year": year_counts[-1][0], "count": year_counts[-1][1]}

        return stats


def main():
    """Main function to demonstrate comprehensive document retrieval."""
    # Initialize the comprehensive retriever
    retriever = ComprehensiveDocRetriever(delay_between_requests=0.5)

    # Example: Retrieve documents for a specific year range
    # Uncomment and modify as needed
    """
    results = retriever.retrieve_all_documents(
        start_year=2023,
        end_year=2024,
        save_to_file=True
    )

    # Get and display summary statistics
    stats = retriever.get_summary_statistics(results)
    retriever.logger.info("Summary Statistics:")
    retriever.logger.info(f"Total years processed: {stats['total_years']}")
    retriever.logger.info(f"Total documents: {stats['total_documents']}")
    if stats['most_productive_year']:
        retriever.logger.info(f"Most productive year: {stats['most_productive_year']['year']} "
                            f"({stats['most_productive_year']['count']} documents)")
    """

    # For testing, just retrieve a small sample
    retriever.logger.info("Starting test retrieval for 2024 (limited)")
    test_results = retriever.retrieve_all_documents(
        start_year=2024,
        end_year=2024,
        save_to_file=True
    )

    # Display summary
    stats = retriever.get_summary_statistics(test_results)
    retriever.logger.info("Test completed successfully!")
    for year, count in stats['documents_per_year'].items():
        retriever.logger.info(f"Year {year}: {count} documents")


if __name__ == '__main__':
    main()