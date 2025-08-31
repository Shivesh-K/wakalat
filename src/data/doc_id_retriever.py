import requests
import re
from base import WakalatLogger, alert_document_retrieval_failure, alert_document_id_extraction_failure
from bs4 import BeautifulSoup
from .constants import DocRetrieverConstants


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
        Now includes alerting for failures.
        """
        try:
            url = self.build_url(year, page)
            response = requests.get(url, timeout=DocRetrieverConstants.REQUEST_TIMEOUT)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")

            # Find all <a> tags with href starting with "/docfragment"
            links = [a["href"] for a in soup.find_all("a", href=True)
                     if a["href"].startswith("/docfragment")]

            # Alert if no docfragment links found (potential issue)
            if not links:
                self.logger.warning(f"No /docfragment links found for year {year}, page {page}")
                alert_document_retrieval_failure(
                    year=year,
                    page=page,
                    url=url,
                    error=Exception("No /docfragment links found in response"),
                    context={
                        "response_length": len(response.content),
                        "status_code": response.status_code
                    }
                )

            return links

        except requests.RequestException as e:
            self.logger.error(f"Error fetching data for year {year}, page {page}: {e}")

            # Send alert for request failures
            alert_document_retrieval_failure(
                year=year,
                page=page,
                url=self.build_url(year, page),
                error=e,
                context={
                    "request_timeout": DocRetrieverConstants.REQUEST_TIMEOUT
                }
            )
            return []

    def get_document_links_with_ids(self, year, page=1):
        """
        Retrieve document fragment links with their extracted IDs.
        Now includes alerting for ID extraction failures.
        """
        links = self.get_document_links(year, page)
        result = []
        failed_extractions = []

        for link in links:
            doc_id = self.extract_document_id(link)
            if doc_id:
                result.append((link, doc_id, year))
            else:
                failed_extractions.append(link)

        # Alert if we have ID extraction failures
        if failed_extractions:
            self.logger.warning(f"Failed to extract IDs from {len(failed_extractions)} links")
            alert_document_id_extraction_failure(
                links_without_ids=failed_extractions,
                year=year,
                page=page,
                context={
                    "total_links": len(links),
                    "successful_extractions": len(result)
                }
            )

        return result
