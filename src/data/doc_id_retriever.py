import requests
import re
from base import WakalatLogger
from bs4 import BeautifulSoup
from constants import DocRetrieverConstants


class DocRetriever:
    def __init__(self):
        """Initialize DocRetriever with logger."""
        self.logger = WakalatLogger("DocRetriever")

    @classmethod
    def build_url(cls, year, page=1):
        """
        Build the complete search URL with year and page parameters.

        Args:
            year (int): The year to search for (e.g., 2024)
            page (int): The page number (default: 1)

        Returns:
            str: Complete URL for the search
        """
        search_path = DocRetrieverConstants.SEARCH_QUERY.format(year=year, page=page)
        return DocRetrieverConstants.DOMAIN_NAME + search_path

    @classmethod
    def build_search_path(cls, year, page=1):
        """
        Build just the search path with parameters.

        Args:
            year (int): The year to search for
            page (int): The page number (default: 1)

        Returns:
            str: Search path with parameters
        """
        return DocRetrieverConstants.SEARCH_QUERY.format(year=year, page=page)

    @classmethod
    def extract_document_id(cls, doc_link):
        """
        Extract document ID from document fragment link.

        Args:
            doc_link (str): Document link like '/docfragment/94564485/?formInput=...'

        Returns:
            str: Document ID (e.g., '94564485') or None if not found
        """
        # Use regex to extract the document ID from the path
        match = re.search(r'/docfragment/(\d+)/', doc_link)
        if match:
            return match.group(1)
        return None

    def get_document_links(self, year, page=1):
        """
        Retrieve document fragment links from a specific year and page.

        Args:
            year (int): The year to search for
            page (int): The page number (default: 1)

        Returns:
            list: List of href links starting with '/docfragment'
        """
        try:
            url = self.build_url(year, page)
            response = requests.get(url)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")

            # Find all <a> tags with href starting with "/docfragment"
            links = [a["href"] for a in soup.find_all("a", href=True)
                     if a["href"].startswith("/docfragment")]

            return links

        except requests.RequestException as e:
            self.logger.error(f"Error fetching data for year {year}, page {page}: {e}")
            return []

    def get_document_links_with_ids(self, year, page=1):
        """
        Retrieve document fragment links with their extracted IDs.

        Args:
            year (int): The year to search for
            page (int): The page number (default: 1)

        Returns:
            list: List of tuples (link, document_id)
        """
        links = self.get_document_links(year, page)
        result = []

        for link in links:
            doc_id = self.extract_document_id(link)
            result.append((link, doc_id))

        return result

    def get_all_document_links_for_year(self, year, max_pages=None):
        """
        Get all document links for a specific year across multiple pages.

        Args:
            year (int): The year to search for
            max_pages (int, optional): Maximum number of pages to fetch

        Returns:
            list: Combined list of all document links for the year
        """
        all_links = []
        page = 1

        while True:
            if max_pages and page > max_pages:
                break

            links = self.get_document_links(year, page)

            if not links:  # No more links found, probably reached end
                break

            all_links.extend(links)
            self.logger.info(f"Year {year}, Page {page}: Found {len(links)} links")
            page += 1

        return all_links

    def get_all_document_links_with_ids_for_year(self, year, max_pages=None):
        """
        Get all document links with IDs for a specific year across multiple pages.

        Args:
            year (int): The year to search for
            max_pages (int, optional): Maximum number of pages to fetch

        Returns:
            list: Combined list of all document (link, id) tuples for the year
        """
        all_links = []
        page = 1

        while True:
            if max_pages and page > max_pages:
                break

            links_with_ids = self.get_document_links_with_ids(year, page)

            if not links_with_ids:  # No more links found, probably reached end
                break

            all_links.extend(links_with_ids)
            self.logger.info(f"Year {year}, Page {page}: Found {len(links_with_ids)} links")
            page += 1

        return all_links

    def process_all_years(self, max_pages_per_year=None):
        """
        Process all years in the defined range and collect document links.

        Args:
            max_pages_per_year (int, optional): Max pages to fetch per year

        Returns:
            dict: Dictionary with year as key and list of links as value
        """
        results = {}

        for year in DocRetrieverConstants.get_year_range():
            self.logger.info(f"Processing year: {year}")
            links = self.get_all_document_links_for_year(year, max_pages_per_year)
            results[year] = links
            self.logger.info(f"Total links found for {year}: {len(links)}")

        return results

    def process_all_years_with_ids(self, max_pages_per_year=None):
        """
        Process all years in the defined range and collect document links with IDs.

        Args:
            max_pages_per_year (int, optional): Max pages to fetch per year

        Returns:
            dict: Dictionary with year as key and list of (link, id) tuples as value
        """
        results = {}

        for year in DocRetrieverConstants.get_year_range():
            self.logger.info(f"Processing year: {year}")
            links_with_ids = self.get_all_document_links_with_ids_for_year(year, max_pages_per_year)
            results[year] = links_with_ids
            self.logger.info(f"Total links found for {year}: {len(links_with_ids)}")

        return results


# Example usage and testing
if __name__ == '__main__':
    retriever = DocRetriever()

    # Test URL building
    retriever.logger.info("Testing URL building:")
    url = DocRetriever.build_url(2024, 1)
    retriever.logger.info(f"URL for 2024, page 1: {url}")

    # Test document ID extraction
    test_link = "/docfragment/94564485/?formInput=doctypes%3A%20supremecourt%20year%3A%202024"
    doc_id = DocRetriever.extract_document_id(test_link)
    retriever.logger.info(f"Extracted document ID from '{test_link}': {doc_id}")

    # Test getting links for a specific year and page
    retriever.logger.info("Testing link retrieval for 2024, page 1:")
    links_with_ids = retriever.get_document_links_with_ids(2024, 1)
    retriever.logger.info(f"Found {len(links_with_ids)} links with IDs:")
    for link, doc_id in links_with_ids[:5]:  # Show first 5 links
        retriever.logger.info(f"  Link: {link}, ID: {doc_id}")

    # Uncomment below to process all years (this will make many HTTP requests)
    # retriever.logger.info("Processing all years:")
    # all_results = retriever.process_all_years_with_ids(max_pages_per_year=2)
    # for year, links_with_ids in all_results.items():
    #     retriever.logger.info(f"Year {year}: {len(links_with_ids)} total links")