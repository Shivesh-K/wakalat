import argparse
from datetime import datetime
from src.data.document_retriever import ComprehensiveDocRetriever
from dotenv import load_dotenv


def main():
    # Get current year
    current_year = datetime.now().year

    # Set up command line argument parsing
    parser = argparse.ArgumentParser(description='Retrieve documents for specified year range')
    parser.add_argument('--start-year', type=int, default=current_year,
                        help=f'Starting year for document retrieval (default: {current_year})')
    parser.add_argument('--end-year', type=int, default=current_year,
                        help=f'Ending year for document retrieval (default: {current_year})')
    parser.add_argument('--delay', type=float, default=0.5,
                        help='Delay between requests in seconds (default: 0.5)')
    parser.add_argument('--save-to-file', action='store_true',
                        help='Save results to file (default: False)')
    parser.add_argument('--save-to-bq', action='store_true', default=True,
                        help='Save results to BigQuery (default: True)')

    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    # Initialize retriever
    retriever = ComprehensiveDocRetriever(delay_between_requests=args.delay)

    # Log the configuration
    retriever.logger.info(f"Starting document retrieval for {args.start_year}-{args.end_year}")
    retriever.logger.info(f"Save to file: {args.save_to_file}, Save to BigQuery: {args.save_to_bq}")

    # Retrieve documents
    results = retriever.retrieve_all_documents(
        start_year=args.start_year,
        end_year=args.end_year,
        save_to_file=args.save_to_file,
        save_to_bq=args.save_to_bq
    )

    # Display summary (uncomment if you want to show statistics)
    # stats = retriever.get_summary_statistics(results)
    retriever.logger.info("Document retrieval completed successfully!")
    # for year, count in stats['documents_per_year'].items():
    #     retriever.logger.info(f"Year {year}: {count} documents")


if __name__ == "__main__":
    main()