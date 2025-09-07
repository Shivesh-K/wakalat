"""
Document Parser using BigQuery AI - Configurable Version

Extracts key arguments, summaries, and structured information from legal judgments
using BigQuery's ML.GENERATE_TEXT function with AI prompts loaded from external files.
"""
import json
import time
import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from pathlib import Path

from google.cloud import bigquery

from base import WakalatLogger
from src.data import BigQueryDocumentWriter


@dataclass
class ParsedDocumentResult:
    """Represents the result of document parsing."""
    doc_id: str
    success: bool
    key_arguments: Optional[List[str]] = None
    summary: Optional[str] = None
    case_details: Optional[Dict[str, Any]] = None
    legal_citations: Optional[List[str]] = None
    judgment_type: Optional[str] = None
    parties_involved: Optional[List[str]] = None
    court_name: Optional[str] = None
    judge_name: Optional[str] = None
    decision_date: Optional[str] = None
    case_number: Optional[str] = None
    legal_areas: Optional[List[str]] = None
    outcome: Optional[str] = None
    error_message: Optional[str] = None
    processing_time_seconds: Optional[float] = None
    content_length: Optional[int] = None


@dataclass
class PromptConfig:
    """Configuration for AI prompts."""
    summary: str
    key_arguments: str
    case_details: str
    legal_citations: str
    temperature: float = 0.2
    max_output_tokens: int = 1024
    content_max_length: int = 8000


class DocumentParser:
    """
    Parses legal documents using BigQuery's AI capabilities to extract
    key arguments, summaries, and structured legal information.
    Uses configurable prompts loaded from external files.
    """

    def __init__(self,
                 project_id: str,
                 dataset_id: str,
                 prompts_config_path: Optional[str] = None,
                 credentials_path: Optional[str] = None):
        """
        Initialize the document parser.

        Args:
            project_id: GCP project ID
            dataset_id: BigQuery dataset ID
            prompts_config_path: Path to prompts configuration file
            credentials_path: Path to service account JSON (optional)
        """
        self.logger = WakalatLogger("DocumentParser")

        self.project_id = project_id
        self.dataset_id = dataset_id
        self.source_table_id = os.getenv("GCP.DETAILS_TABLE_ID")
        self.parsed_table_id = os.getenv("GCP.PARSED_TABLE_ID")
        self.bq_writer = BigQueryDocumentWriter(
            project_id=os.getenv('GCP.PROJECT_ID'),
            dataset_id=os.getenv('GCP.DATASET_ID'),
            table_id=os.getenv('GCP.TABLE_ID'),
            credentials_path=os.getenv('GCP.CREDENTIALS_PATH')
        )

        # Load prompt configuration
        self.prompt_config = self._load_prompt_config(prompts_config_path)

        # Initialize BigQuery client
        if credentials_path:
            self.client = bigquery.Client.from_service_account_json(
                credentials_path,
                project=project_id
            )
        else:
            self.client = bigquery.Client(project=project_id)

    def _load_prompt_config(self, config_path: Optional[str]) -> PromptConfig:
        """
        Load prompt configuration from file or use defaults.

        Args:
            config_path: Path to configuration file

        Returns:
            PromptConfig object
        """
        if not config_path:
            config_path = os.path.join(os.path.dirname(__file__), "prompts_config.json")

        config_file = Path(config_path)

        # Default configuration
        default_config = {
            "summary": {
                "prompt": "Please provide a concise summary (2-3 paragraphs) of this legal judgment. Focus on the key issues, main arguments, and the court's decision.",
                "temperature": 0.2,
                "max_output_tokens": 1024
            },
            "key_arguments": {
                "prompt": "Extract the main legal arguments from this judgment. List them as numbered points (1., 2., 3., etc.). Focus on the core legal reasoning and key points made by the court.",
                "temperature": 0.3,
                "max_output_tokens": 512
            },
            "case_details": {
                "prompt": "Extract structured information from this legal document in JSON format. Include: court_name, judge_name, case_number, decision_date, parties_involved (as array), judgment_type, outcome, legal_areas (as array). Only include information explicitly mentioned in the document.",
                "temperature": 0.1,
                "max_output_tokens": 512
            },
            "legal_citations": {
                "prompt": "Extract all legal case citations mentioned in this document. List each citation on a separate line. Include case names, court citations, and statutory references.",
                "temperature": 0.2,
                "max_output_tokens": 512
            },
            "global_settings": {
                "content_max_length": 8000,
                "flatten_json_output": True
            }
        }

        try:
            if config_file.exists():
                self.logger.info(f"Loading prompts configuration from {config_path}")
                with open(config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)

                # Merge with defaults
                config = {**default_config, **loaded_config}
            else:
                self.logger.info(f"Config file not found at {config_path}, creating default configuration")
                config = default_config

                # Create default config file
                config_file.parent.mkdir(parents=True, exist_ok=True)
                with open(config_file, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
                self.logger.info(f"Created default configuration file at {config_path}")

            # Create PromptConfig object
            global_settings = config.get("global_settings", {})

            return PromptConfig(
                summary=config["summary"]["prompt"],
                key_arguments=config["key_arguments"]["prompt"],
                case_details=config["case_details"]["prompt"],
                legal_citations=config["legal_citations"]["prompt"],
                temperature=global_settings.get("temperature", 0.2),
                max_output_tokens=global_settings.get("max_output_tokens", 1024),
                content_max_length=global_settings.get("content_max_length", 8000)
            )

        except Exception as e:
            self.logger.error(f"Error loading prompt configuration: {e}")
            self.logger.info("Using fallback default prompts")

            # Return minimal default configuration
            return PromptConfig(
                summary="Provide a concise summary of this legal judgment.",
                key_arguments="Extract the main legal arguments from this judgment.",
                case_details="Extract structured information in JSON format.",
                legal_citations="Extract all legal case citations."
            )

    def reload_prompt_config(self, config_path: Optional[str] = None) -> bool:
        """
        Reload prompt configuration from file.

        Args:
            config_path: Path to configuration file

        Returns:
            True if reloaded successfully
        """
        old_config = self.prompt_config
        try:
            self.prompt_config = self._load_prompt_config(config_path)
            self.logger.info("Successfully reloaded prompt configuration")
            return True
        except Exception as e:
            self.logger.error(f"Failed to reload prompt configuration: {e}")
            # Keep old configuration
            self.prompt_config = old_config
            return False

    def parse_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        Parse a single document using BigQuery AI to extract key information.

        Args:
            doc_id: Document ID to parse

        Returns:
            Dictionary with parsing results or None if failed
        """
        start_time = time.time()

        try:
            self.logger.debug(f"Starting AI parsing for document {doc_id}")

            # Check if already parsed
            if self.bq_writer.is_document_parsed(doc_id):
                self.logger.debug(f"Document {doc_id} already parsed successfully")
                return {"success": True, "message": "Already parsed"}

            # Parse the document using AI
            parse_result = self._parse_with_ai(doc_id)

            if not parse_result:
                self.logger.warning(f"AI parsing returned no results for {doc_id}")
                return {"success": False, "error": "AI parsing returned no results"}

            # Save parsed results to BigQuery
            save_success = self._save_parsed_document(parse_result)

            if not save_success:
                self.logger.error(f"Failed to save parsed results for {doc_id}")
                return {"success": False, "error": "Failed to save parsed results"}

            processing_time = time.time() - start_time
            self.logger.debug(f"Successfully parsed document {doc_id} in {processing_time:.2f}s")

            return {
                "success": True,
                "doc_id": doc_id,
                "processing_time": processing_time,
                "summary_length": len(parse_result.summary) if parse_result.summary else 0,
                "key_arguments_count": len(parse_result.key_arguments) if parse_result.key_arguments else 0
            }

        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"Error parsing document {doc_id}: {str(e)}"
            self.logger.error(error_msg)

            # Save error result
            error_result = ParsedDocumentResult(
                doc_id=doc_id,
                success=False,
                error_message=str(e),
                processing_time_seconds=processing_time
            )

            try:
                self._save_parsed_document(error_result)
            except Exception as save_error:
                self.logger.error(f"Could not save error result for {doc_id}: {save_error}")

            return {"success": False, "error": str(e)}

    def parse_unparsed_documents(self, limit: int = 50) -> Dict[str, Any]:
        """
        Parse documents that have not yet been parsed successfully.

        Args:
            limit: Maximum number of documents to parse

        Returns:
            Dictionary with parsing results
        """
        try:
            # Find unparsed document IDs
            docs_to_parse = self.bq_writer.get_unparsed_documents(10)
            if not docs_to_parse:
                return {
                    "message": "No unparsed documents found",
                    "total_processed": 0,
                    "successful": 0,
                    "failed": 0
                }

            self.logger.info(f"Parsing {len(docs_to_parse)} unparsed documents")

            successful = 0
            failed = 0
            results = []

            for doc_id in docs_to_parse:
                try:
                    self.logger.debug(f"Parsing unparsed document {doc_id}")
                    result = self.parse_document(doc_id)

                    if result and result.get("success"):
                        successful += 1
                    else:
                        failed += 1

                    results.append({"doc_id": doc_id, **(result or {})})

                except Exception as e:
                    self.logger.error(f"Error parsing unparsed doc {doc_id}: {e}")
                    failed += 1
                    results.append({"doc_id": doc_id, "success": False, "error": str(e)})

            return {
                "total_processed": len(docs_to_parse),
                "successful": successful,
                "failed": failed,
                "success_rate": round((successful / len(docs_to_parse)) * 100, 2),
                "results": results
            }

        except Exception as e:
            self.logger.error(f"Error in parse_unparsed_documents: {e}")
            return {"error": str(e)}


    def _parse_with_ai(self, doc_id: str) -> Optional[ParsedDocumentResult]:
        """
        Use BigQuery AI to parse document content and extract structured information.

        Args:
            doc_id: Document ID to parse

        Returns:
            ParsedDocumentResult with extracted information
        """
        try:
            # Build dynamic query using configured prompts
            content_length = self.prompt_config.content_max_length

            query = f"""
            WITH document_content AS (
                SELECT 
                    doc_id,
                    content,
                    CHAR_LENGTH(content) as content_length
                FROM `{self.project_id}.{self.dataset_id}.{self.source_table_id}`
                WHERE doc_id = @doc_id
                AND content IS NOT NULL
                AND CHAR_LENGTH(content) > 100
            ),
            ai_analysis AS (
                SELECT 
                    doc_id,
                    content_length,
                    -- Extract summary
                    ML.GENERATE_TEXT(
                        MODEL `{self.project_id}.{self.dataset_id}.text_generation_model`,
                        (
                            SELECT CONCAT(
                                '{self.prompt_config.summary} ',
                                'Legal Document Content: ', 
                                SUBSTR(content, 1, {content_length})
                            ) as prompt
                        ),
                        STRUCT(
                            {self.prompt_config.temperature} AS temperature,
                            {self.prompt_config.max_output_tokens} AS max_output_tokens,
                            TRUE AS flatten_json_output
                        )
                    ).ml_generate_text_result AS summary,

                    -- Extract key arguments
                    ML.GENERATE_TEXT(
                        MODEL `{self.project_id}.{self.dataset_id}.text_generation_model`,
                        (
                            SELECT CONCAT(
                                '{self.prompt_config.key_arguments} ',
                                'Legal Document Content: ', 
                                SUBSTR(content, 1, {content_length})
                            ) as prompt
                        ),
                        STRUCT(
                            0.3 AS temperature,
                            512 AS max_output_tokens
                        )
                    ).ml_generate_text_result AS key_arguments_raw,

                    -- Extract structured case details
                    ML.GENERATE_TEXT(
                        MODEL `{self.project_id}.{self.dataset_id}.text_generation_model`,
                        (
                            SELECT CONCAT(
                                '{self.prompt_config.case_details} ',
                                'Legal Document Content: ', 
                                SUBSTR(content, 1, {content_length})
                            ) as prompt
                        ),
                        STRUCT(
                            0.1 AS temperature,
                            512 AS max_output_tokens,
                            TRUE AS flatten_json_output
                        )
                    ).ml_generate_text_result AS case_details_raw,

                    -- Extract legal citations
                    ML.GENERATE_TEXT(
                        MODEL `{self.project_id}.{self.dataset_id}.text_generation_model`,
                        (
                            SELECT CONCAT(
                                '{self.prompt_config.legal_citations} ',
                                'Legal Document Content: ', 
                                SUBSTR(content, 1, {content_length})
                            ) as prompt
                        ),
                        STRUCT(
                            0.2 AS temperature,
                            512 AS max_output_tokens
                        )
                    ).ml_generate_text_result AS citations_raw

                FROM document_content
            )
            SELECT 
                doc_id,
                content_length,
                summary,
                key_arguments_raw,
                case_details_raw,
                citations_raw
            FROM ai_analysis
            """

            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("doc_id", "STRING", doc_id)
                ]
            )

            query_job = self.client.query(query, job_config=job_config)
            results = list(query_job.result())

            if not results:
                self.logger.warning(f"No content found for document {doc_id}")
                return None

            row = results[0]

            # Process the AI results
            result = ParsedDocumentResult(
                doc_id=doc_id,
                success=True,
                content_length=row.content_length
            )

            # Process summary
            result.summary = self._clean_text(row.summary) if row.summary else None

            # Process key arguments
            if row.key_arguments_raw:
                result.key_arguments = self._extract_list_from_text(row.key_arguments_raw)

            # Process case details JSON
            if row.case_details_raw:
                try:
                    case_details = json.loads(row.case_details_raw)
                    result.case_details = case_details

                    # Extract individual fields from JSON
                    result.court_name = case_details.get('court_name')
                    result.judge_name = case_details.get('judge_name')
                    result.case_number = case_details.get('case_number')
                    result.decision_date = case_details.get('decision_date')
                    result.judgment_type = case_details.get('judgment_type')
                    result.outcome = case_details.get('outcome')
                    result.parties_involved = case_details.get('parties_involved', [])
                    result.legal_areas = case_details.get('legal_areas', [])

                except json.JSONDecodeError:
                    # If JSON parsing fails, try to extract manually
                    result.case_details = {"raw": row.case_details_raw}
                    self.logger.warning(f"Could not parse case details JSON for {doc_id}")

            # Process legal citations
            if row.citations_raw:
                result.legal_citations = self._extract_list_from_text(row.citations_raw)

            return result

        except Exception as e:
            self.logger.error(f"Error in AI parsing for {doc_id}: {e}")
            return ParsedDocumentResult(
                doc_id=doc_id,
                success=False,
                error_message=str(e)
            )

    def _clean_text(self, text: str) -> str:
        """Clean and normalize extracted text."""
        if not text:
            return ""

        # Remove extra whitespace and normalize
        cleaned = " ".join(text.split())

        # Remove common AI response prefixes
        prefixes_to_remove = [
            "Here is a summary:",
            "Summary:",
            "Here are the key arguments:",
            "Key arguments:",
            "The main arguments are:",
        ]

        for prefix in prefixes_to_remove:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()

        return cleaned

    def _extract_list_from_text(self, text: str) -> List[str]:
        """Extract a list of items from AI-generated text."""
        if not text:
            return []

        items = []
        lines = text.split('\n')

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Remove numbering (1., 2., -, *, etc.)
            import re
            cleaned_line = re.sub(r'^[\d\-\*\•]+[\.\)]\s*', '', line).strip()

            if cleaned_line and len(cleaned_line) > 3:  # Avoid very short items
                items.append(cleaned_line)

        return items[:20]  # Limit to 20 items maximum

    def _save_parsed_document(self, result: ParsedDocumentResult) -> bool:
        """
        Save parsed document result to BigQuery.

        Args:
            result: ParsedDocumentResult to save

        Returns:
            True if saved successfully
        """
        try:
            # Prepare data for BigQuery
            return self.bq_writer.insert_parsed_document_details(result.__dict__)
        except Exception as e:
            self.logger.error(f"Error saving parsed document {result.doc_id}: {e}")
            return False

    def get_parsing_stats(self) -> Dict[str, Any]:
        """
        Get statistics about document parsing progress.

        Returns:
            Dictionary with parsing statistics
        """
        try:
            query = f"""
            WITH parsing_stats AS (
                SELECT
                    COUNT(*) as total_parsed,
                    COUNT(CASE WHEN success THEN 1 END) as successful_parsed,
                    COUNT(CASE WHEN NOT success THEN 1 END) as failed_parsed,
                    AVG(CASE WHEN success THEN processing_time_seconds END) as avg_processing_time,
                    AVG(CASE WHEN success THEN content_length END) as avg_content_length,
                    AVG(CASE WHEN success THEN ARRAY_LENGTH(key_arguments) END) as avg_key_arguments,
                    MIN(parsed_at) as first_parsed,
                    MAX(parsed_at) as last_parsed
                FROM `{self.project_id}.{self.dataset_id}.{self.parsed_table_id}`
            ),
            source_stats AS (
                SELECT COUNT(*) as total_documents
                FROM `{self.project_id}.{self.dataset_id}.{self.source_table_id}`
                WHERE content IS NOT NULL
            )
            SELECT
                p.*,
                s.total_documents,
                ROUND((p.total_parsed / s.total_documents) * 100, 2) as completion_percentage
            FROM parsing_stats p
            CROSS JOIN source_stats s
            """

            query_job = self.client.query(query)
            results = list(query_job.result())

            if results:
                row = results[0]
                return {
                    "total_documents_available": row.total_documents,
                    "total_parsed": row.total_parsed,
                    "successful_parsed": row.successful_parsed,
                    "failed_parsed": row.failed_parsed,
                    "success_rate": round((row.successful_parsed / row.total_parsed) * 100,
                                          2) if row.total_parsed > 0 else 0,
                    "completion_percentage": row.completion_percentage,
                    "avg_processing_time_seconds": round(row.avg_processing_time, 2) if row.avg_processing_time else 0,
                    "avg_content_length": int(row.avg_content_length) if row.avg_content_length else 0,
                    "avg_key_arguments_per_document": round(row.avg_key_arguments, 1) if row.avg_key_arguments else 0,
                    "first_parsed": row.first_parsed.isoformat() if row.first_parsed else None,
                    "last_parsed": row.last_parsed.isoformat() if row.last_parsed else None
                }

            return {"error": "No parsing statistics available"}

        except Exception as e:
            self.logger.error(f"Error getting parsing stats: {e}")
            return {"error": str(e)}

    def reparse_failed_documents(self, limit: Optional[int] = 50) -> Dict[str, Any]:
        """
        Retry parsing for documents that previously failed.

        Args:
            limit: Maximum number of documents to reparse

        Returns:
            Dictionary with reparse results
        """
        try:
            # Get failed document IDs
            query = f"""
            SELECT doc_id
            FROM `{self.project_id}.{self.dataset_id}.{self.parsed_table_id}`
            WHERE success = FALSE
            ORDER BY parsed_at DESC
            LIMIT {limit or 50}
            """

            query_job = self.client.query(query)
            failed_docs = [row.doc_id for row in query_job.result()]

            if not failed_docs:
                return {
                    "message": "No failed documents to reparse",
                    "total_processed": 0,
                    "successful": 0,
                    "failed": 0
                }

            self.logger.info(f"Reparsing {len(failed_docs)} failed documents")

            successful = 0
            failed = 0

            for doc_id in failed_docs:
                try:
                    # Delete existing failed record
                    delete_query = f"""
                    DELETE FROM `{self.project_id}.{self.dataset_id}.{self.parsed_table_id}`
                    WHERE doc_id = @doc_id
                    """

                    job_config = bigquery.QueryJobConfig(
                        query_parameters=[
                            bigquery.ScalarQueryParameter("doc_id", "STRING", doc_id)
                        ]
                    )

                    self.client.query(delete_query, job_config=job_config)

                    # Reparse the document
                    result = self.parse_document(doc_id)

                    if result and result.get('success'):
                        successful += 1
                    else:
                        failed += 1

                except Exception as e:
                    self.logger.error(f"Error reparsing {doc_id}: {e}")
                    failed += 1

            return {
                "total_processed": len(failed_docs),
                "successful": successful,
                "failed": failed,
                "success_rate": round((successful / len(failed_docs)) * 100, 2) if failed_docs else 0
            }

        except Exception as e:
            self.logger.error(f"Error in reparse_failed_documents: {e}")
            return {"error": str(e)}

    def get_current_prompts(self) -> Dict[str, Any]:
        """
        Get the currently loaded prompt configuration.

        Returns:
            Dictionary with current prompt settings
        """
        return {
            "summary_prompt": self.prompt_config.summary,
            "key_arguments_prompt": self.prompt_config.key_arguments,
            "case_details_prompt": self.prompt_config.case_details,
            "legal_citations_prompt": self.prompt_config.legal_citations,
            "temperature": self.prompt_config.temperature,
            "max_output_tokens": self.prompt_config.max_output_tokens,
            "content_max_length": self.prompt_config.content_max_length
        }

    def update_prompt_config(self, **kwargs) -> bool:
        """
        Update specific prompt configuration values.

        Args:
            **kwargs: Configuration values to update

        Returns:
            True if updated successfully
        """
        try:
            for key, value in kwargs.items():
                if hasattr(self.prompt_config, key):
                    setattr(self.prompt_config, key, value)
                    self.logger.info(f"Updated prompt config: {key} = {value}")
                else:
                    self.logger.warning(f"Unknown prompt config key: {key}")

            return True
        except Exception as e:
            self.logger.error(f"Error updating prompt config: {e}")
            return False