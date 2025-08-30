"""
Constants for Document Retriever

This file contains configuration constants used throughout the document retrieval system.
"""


class DocRetrieverConstants:
    """Constants for document retrieval operations."""

    # Base domain for the document source
    DOMAIN_NAME = "https://indiankanoon.org"

    # Search query template - modify this based on your actual website structure
    # {year} and {page} will be replaced with actual values
    SEARCH_QUERY = "/search?formInput=year:{year} doctypes:supremecourt&pagenum={page}"

    # Year range for document retrieval
    START_YEAR = 2020
    END_YEAR = 2024

    @classmethod
    def get_year_range(cls):
        """
        Get the range of years to process.

        Returns:
            range: Range object from START_YEAR to END_YEAR (inclusive)
        """
        return range(cls.START_YEAR, cls.END_YEAR + 1)

    # HTTP request settings
    REQUEST_TIMEOUT = 30  # seconds
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # seconds

    # Rate limiting
    DEFAULT_DELAY_BETWEEN_REQUESTS = 1.0  # seconds

    # File output settings
    OUTPUT_DIRECTORY = "retrieved_documents"
    MAX_DOCUMENTS_PER_FILE = 10000