"""
Main entry point for the document retrieval system.

This file demonstrates how to use the system with proper imports.
"""

import sys
import os

# Add the project root to Python path if needed
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Now we can import from anywhere in the project
from base import WakalatLogger
from src.data import DocRetrieverConstants, DocRetriever


def main():
    """Main function demonstrating the document retrieval system."""
    # Initialize logger
    logger = WakalatLogger("MainApplication")
    logger.info("Starting document retrieval application")

    try:
        # Initialize document retriever
        retriever = DocRetriever()
        logger.info("Document retriever initialized successfully")

        # Test document ID extraction
        test_link = "/docfragment/94564485/?formInput=doctypes%3A%20supremecourt%20year%3A%202024"
        doc_id = DocRetriever.extract_document_id(test_link)
        logger.info(f"Extracted document ID: {doc_id}")

        # Test getting year range from constants
        year_range = DocRetrieverConstants.get_year_range()
        logger.info(f"Processing years: {list(year_range)}")

        # Example: Get documents for 2024, page 1
        logger.info("Retrieving documents for 2024, page 1...")
        documents = retriever.get_document_links_with_ids(2024, 1)
        logger.info(f"Found {len(documents)} documents")

        # Display first few documents
        for i, (link, doc_id) in enumerate(documents[:3]):
            logger.info(f"Document {i + 1}: ID={doc_id}")

    except Exception as e:
        logger.error(f"Error in main application: {e}")
        logger.exception("Full traceback:")
        return 1

    logger.info("Application completed successfully")
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)