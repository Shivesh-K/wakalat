"""
Usage Examples for Enhanced Document Retrieval System

This script demonstrates how to use the enhanced document retrieval system
to fetch document details and store them in BigQuery.
"""

from src.data.document_retriever import ComprehensiveDocRetriever
import os
from dotenv import load_dotenv

load_dotenv()

def example_1_fetch_single_document():
    """Example: Fetch details for a single document ID."""
    print("=== Example 1: Fetch Single Document Details ===")

    retriever = ComprehensiveDocRetriever(delay_between_requests=1.0)

    # Replace with actual document ID from your system
    doc_id = "94564485"  # Example ID

    print(f"Fetching details for document ID: {doc_id}")
    details = retriever.fetch_document_details(doc_id, save_to_bq=True)

    if details:
        print("✅ Successfully fetched document details!")
        print(f"Title: {details.get('title', 'N/A')}")
        print(f"Content length: {len(details.get('content', ''))} characters")
        print(f"HTML length: {len(details.get('raw_html', ''))} characters")
        print(f"Metadata keys: {list(details.get('metadata', {}).keys())}")
    else:
        print("❌ Failed to fetch document details")


def example_2_fetch_batch_of_missing_documents():
    """Example: Fetch details for multiple documents that are missing details."""
    print("\n=== Example 2: Fetch Batch of Missing Documents ===")

    retriever = ComprehensiveDocRetriever(delay_between_requests=0.5)

    # Fetch details for up to 20 documents that don't have details yet
    summary = retriever.fetch_missing_document_details(
        batch_size=5,  # Process 5 at a time
        max_documents=20  # Limit to 20 documents
    )

    print("Batch Processing Summary:")
    print(f"Total processed: {summary['total_processed']}")
    print(f"Successful: {summary['successful']}")
    print(f"Failed: {summary['failed']}")
    print(f"Success rate: {summary['success_rate']:.2f}%")
    print(f"Duration: {summary['duration']}")


def example_3_system_status():
    """Example: Check system status and statistics."""
    print("\n=== Example 3: System Status ===")

    retriever = ComprehensiveDocRetriever()
    status = retriever.get_system_status()

    print("System Status:")
    print(f"Timestamp: {status.get('timestamp', 'N/A')}")

    if "bigquery_stats" in status:
        stats = status["bigquery_stats"]

        if "links" in stats:
            links_stats = stats["links"]
            print(f"\nLinks Table:")
            print(f"  Total documents: {links_stats.get('total_links', 0)}")
            print(f"  Years covered: {links_stats.get('years_covered', 0)}")
            print(f"  Year range: {links_stats.get('earliest_year', 'N/A')} - {links_stats.get('latest_year', 'N/A')}")

        if "details" in stats:
            details_stats = stats["details"]
            print(f"\nDetails Table:")
            print(f"  Total documents with details: {details_stats.get('total_details', 0)}")
            print(f"  Average content length: {details_stats.get('avg_content_length', 0):.0f} characters")
            print(f"  Max content length: {details_stats.get('max_content_length', 0)} characters")
            print(f"  Documents with titles: {details_stats.get('documents_with_titles', 0)}")

        if "completion_percentage" in stats:
            print(f"\nCompletion Rate: {stats['completion_percentage']}%")


def example_4_complete_workflow():
    """Example: Complete workflow - retrieve links then fetch details."""
    print("\n=== Example 4: Complete Workflow ===")

    retriever = ComprehensiveDocRetriever(delay_between_requests=0.5)

    # Step 1: Retrieve document links for a specific year
    print("Step 1: Retrieving document links...")
    results = retriever.retrieve_all_documents(
        start_year=2024,
        end_year=2024,
        save_to_file=True,
        save_to_bq=True
    )

    print(f"Retrieved {len(results)} document links")

    # Step 2: Fetch details for the first few documents
    print("\nStep 2: Fetching details for first 3 documents...")
    for i, (link, doc_id, year) in enumerate(results[:3]):
        print(f"Fetching details for document {i + 1}: {doc_id}")
        details = retriever.fetch_document_details(doc_id, save_to_bq=True)
        if details:
            print(f"  ✅ Success - Title: {details.get('title', 'N/A')[:50]}...")
        else:
            print(f"  ❌ Failed")


def check_environment():
    """Check if required environment variables are set."""
    required_vars = [
        'GCP.PROJECT_ID',
        'GCP.DATASET_ID',
        'GCP.TABLE_ID',
        'GCP.CREDENTIALS_PATH'
    ]

    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"  - {var}")
        return False

    print("✅ All required environment variables are set")
    return True


if __name__ == "__main__":
    print("Document Retrieval System - Usage Examples")
    print("=" * 50)

    # Check environment first
    if not check_environment():
        print("\nPlease set the required environment variables before running.")
        exit(1)

    # Run examples
    try:
        # Uncomment the examples you want to run:

        example_1_fetch_single_document()
        # example_2_fetch_batch_of_missing_documents()
        # example_3_system_status()
        # example_4_complete_workflow()

    except KeyboardInterrupt:
        print("\n\n⚠️  Operation cancelled by user")
    except Exception as e:
        print(f"\n❌ Error running examples: {e}")
        raise