import requests
import re
from datetime import datetime
from base import WakalatLogger, alert_document_retrieval_failure, alert_document_id_extraction_failure, \
    alert_system_error
from bs4 import BeautifulSoup
from .constants import DocRetrieverConstants
from typing import Optional, Dict, Any


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
    def build_document_url(cls, doc_id: str) -> str:
        """
        Build the complete document URL for a specific document ID.

        Args:
            doc_id (str): The document ID

        Returns:
            str: Complete URL for the document
        """
        return f"{DocRetrieverConstants.DOMAIN_NAME}/doc/{doc_id}"

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

    def fetch_document_details(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch full document details for a specific document ID.

        Args:
            doc_id (str): The document ID to fetch

        Returns:
            Dict[str, Any]: Document details including content, metadata, etc.
            None: If document could not be fetched or parsed
        """
        url = self.build_document_url(doc_id)
        try:
            self.logger.info(f"Fetching document details for ID: {doc_id}")

            response = requests.get(url, timeout=DocRetrieverConstants.REQUEST_TIMEOUT)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")

            # Extract document details
            document_details = self._parse_document_content(soup, doc_id, url)

            if not document_details:
                self.logger.warning(f"No content extracted for document ID: {doc_id}")
                return None

            self.logger.info(f"Successfully fetched document {doc_id}")
            return document_details

        except requests.RequestException as e:
            self.logger.error(f"Error fetching document {doc_id}: {e}")
            alert_document_retrieval_failure(
                year=None,  # Year not applicable for individual document fetch
                page=None,
                url=url,
                error=e,
                context={
                    "doc_id": doc_id,
                    "operation": "fetch_document_details"
                }
            )
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error processing document {doc_id}: {e}")
            alert_system_error(
                component="document_details_parsing",
                error=e,
                context={
                    "doc_id": doc_id,
                    "url": url
                }
            )
            return None

    def _parse_document_content(self, soup: BeautifulSoup, doc_id: str, url: str) -> Optional[Dict[str, Any]]:
        """
        Parse document content from BeautifulSoup object.

        Args:
            soup (BeautifulSoup): Parsed HTML content
            doc_id (str): Document ID
            url (str): Document URL

        Returns:
            Dict[str, Any]: Parsed document details
        """
        try:
            # Initialize document details structure
            document_details = {
                "doc_id": doc_id,
                "url": url,
                "title": None,
                "content": None,
                "metadata": {},
                "raw_html": str(soup),
                "extracted_at": None
            }

            # Extract title (adjust selector based on actual HTML structure)
            title_element = soup.find(".document_title")
            if title_element:
                document_details["title"] = title_element.get_text(strip=True)

            # Try to find main content (adjust selectors based on actual HTML structure)
            # Common selectors for legal documents - you may need to customize these
            content_selectors = [
                "#pre_1"
            ]

            content_text = ""
            for selector in content_selectors:
                content_element = soup.select_one(selector)
                if content_element:
                    content_text = content_element.get_text(strip=True, separator='\n')
                    break

            # If no specific content found, extract from body but filter out navigation
            if not content_text:
                body = soup.find("body")
                if body:
                    # Remove script, style, nav, header, footer elements
                    for element in body(["script", "style", "nav", "header", "footer", "aside"]):
                        element.decompose()
                    content_text = body.get_text(strip=True, separator='\n')

            document_details["content"] = content_text

            # Extract metadata (customize based on actual document structure)
            metadata = {}

            # Look for common metadata patterns
            meta_tags = soup.find_all("meta")
            for meta in meta_tags:
                if meta.get("name") and meta.get("content"):
                    metadata[meta.get("name")] = meta.get("content")

            # Look for date information
            date_patterns = [
                r'Date[:\s]*(\d{1,2}[-/]\d{1,2}[-/]\d{4})',
                r'(\d{1,2}[-/]\d{1,2}[-/]\d{4})',
                r'Date[:\s]*(\d{1,2}\s\w+\s\d{4})'
            ]

            for pattern in date_patterns:
                match = re.search(pattern, content_text)
                if match:
                    metadata["extracted_date"] = match.group(1)
                    break

            # Look for court information
            court_match = re.search(r'(Supreme Court|High Court|District Court)', content_text, re.IGNORECASE)
            if court_match:
                metadata["court"] = court_match.group(1)

            # Look for case number patterns
            case_patterns = [
                r'Case No[.:\s]*([A-Z0-9\/\-\s]+)',
                r'Writ Petition[:\s]*([A-Z0-9\/\-\s]+)',
                r'Civil Appeal[:\s]*([A-Z0-9\/\-\s]+)'
            ]

            for pattern in case_patterns:
                match = re.search(pattern, content_text, re.IGNORECASE)
                if match:
                    metadata["case_number"] = match.group(1).strip()
                    break

            document_details["metadata"] = metadata
            document_details["extracted_at"] = datetime.now().isoformat(sep=' ')

            # Validate that we have meaningful content
            if not content_text or len(content_text.strip()) < 100:
                self.logger.warning(f"Document {doc_id} has minimal content (length: {len(content_text)})")
                return None

            return document_details

        except Exception as e:
            self.logger.error(f"Error parsing document content for {doc_id}: {e}")
            return None