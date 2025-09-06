"""
Alert System for Document Retrieval System

This module provides a comprehensive alerting system for edge cases
that require manual developer attention.
"""

import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from enum import Enum
import json
import traceback
import os
import socket
import logging
from contextlib import contextmanager
from .logger import WakalatLogger


class AlertSeverity(Enum):
    """Alert severity levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertType(Enum):
    """Types of alerts that can be raised."""
    DOCUMENT_RETRIEVAL_FAILURE = "DOCUMENT_RETRIEVAL_FAILURE"
    DOCUMENT_ID_EXTRACTION_FAILURE = "DOCUMENT_ID_EXTRACTION_FAILURE"
    DATABASE_WRITE_FAILURE = "DATABASE_WRITE_FAILURE"
    DATABASE_CONNECTION_FAILURE = "DATABASE_CONNECTION_FAILURE"
    BIGQUERY_FAILURE = "BIGQUERY_FAILURE"
    NETWORK_FAILURE = "NETWORK_FAILURE"
    PARSING_FAILURE = "PARSING_FAILURE"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    SYSTEM_ERROR = "SYSTEM_ERROR"
    DATA_VALIDATION_FAILURE = "DATA_VALIDATION_FAILURE"


class EmailConnectionError(Exception):
    """Custom exception for email connection issues."""
    pass


class WakalatAlertSystem:
    """
    Alert system for sending notifications about system failures and edge cases.

    Enhanced with modern Python best practices and robust error handling.
    """
    if os.getenv('ENVIRONMENT') == 'production':
        # Default recipient emails
        DEFAULT_RECIPIENTS = [
            "ballanisunil123@gmail.com",
            "divyanshbhatiajm19@gmail.com",
            "shivesh.kaundinya@gmail.com"
        ]
    else:
        DEFAULT_RECIPIENTS = ['divyanshbhatiassa0417@gmail.com']

    def __init__(self,
                 smtp_server: str = "smtp.gmail.com",
                 smtp_port: int = 587,
                 sender_email: Optional[str] = None,
                 sender_password: Optional[str] = None,
                 recipients: Optional[List[str]] = None,
                 use_tls: bool = True,
                 timeout: int = 30):
        """
        Initialize the alert system.

        Args:
            smtp_server: SMTP server address
            smtp_port: SMTP server port
            sender_email: Email address to send alerts from
            sender_password: Password or app password for sender email
            recipients: List of email addresses to receive alerts
            use_tls: Whether to use TLS encryption
            timeout: SMTP connection timeout in seconds
        """
        self.logger = WakalatLogger("WakalatAlertSystem")

        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.use_tls = use_tls
        self.timeout = timeout

        # Get email credentials from environment variables if not provided
        self.sender_email = sender_email or os.getenv('ALERT_SENDER_EMAIL')
        self.sender_password = sender_password or os.getenv('ALERT_SENDER_PASSWORD')

        self.recipients = recipients or self.DEFAULT_RECIPIENTS.copy()

        # Validate configuration
        if not self.sender_email or not self.sender_password:
            self.logger.warning(
                "Email credentials not provided. Set ALERT_SENDER_EMAIL and "
                "ALERT_SENDER_PASSWORD environment variables or pass them explicitly."
            )

        # Email validation patterns
        import re
        self.email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

    def _validate_email(self, email: str) -> bool:
        """Validate email address format."""
        return bool(self.email_pattern.match(email.strip()))

    def _validate_recipients(self, recipients: List[str]) -> List[str]:
        """Validate and filter recipient email addresses."""
        valid_recipients = []
        for email in recipients:
            email = email.strip()
            if self._validate_email(email):
                valid_recipients.append(email)
            else:
                self.logger.warning(f"Invalid email address: {email}")

        if not valid_recipients:
            raise ValueError("No valid recipient email addresses provided")

        return valid_recipients

    @contextmanager
    def _smtp_connection(self):
        """Context manager for SMTP connection with proper cleanup."""
        server = None
        try:
            # Create SMTP connection
            if self.smtp_port == 465:  # SSL
                context = ssl.create_default_context()
                server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port,
                                        context=context, timeout=self.timeout)
            else:  # Regular SMTP with optional TLS
                server = smtplib.SMTP(self.smtp_server, self.smtp_port,
                                    timeout=self.timeout)
                if self.use_tls:
                    context = ssl.create_default_context()
                    server.starttls(context=context)

            # Login if credentials provided
            if self.sender_email and self.sender_password:
                server.login(self.sender_email, self.sender_password)

            yield server

        except smtplib.SMTPAuthenticationError as e:
            raise EmailConnectionError(f"SMTP authentication failed: {e}") from e
        except smtplib.SMTPConnectError as e:
            raise EmailConnectionError(f"Failed to connect to SMTP server: {e}") from e
        except smtplib.SMTPRecipientsRefused as e:
            raise EmailConnectionError(f"Recipients refused: {e}") from e
        except socket.timeout as e:
            raise EmailConnectionError(f"SMTP connection timeout: {e}") from e
        except Exception as e:
            raise EmailConnectionError(f"SMTP connection error: {e}") from e
        finally:
            if server:
                try:
                    server.quit()
                except Exception as e:
                    self.logger.warning(f"Error closing SMTP connection: {e}")

    def send_alert(self,
                   alert_type: AlertType,
                   severity: AlertSeverity,
                   title: str,
                   message: str,
                   context: Optional[Dict[str, Any]] = None,
                   exception: Optional[Exception] = None,
                   recipients: Optional[List[str]] = None) -> bool:
        """
        Send an alert email to the specified recipients.

        Args:
            alert_type: Type of alert being raised
            severity: Severity level of the alert
            title: Brief title/subject of the alert
            message: Detailed message describing the issue
            context: Additional context data (dict)
            exception: Exception object if applicable
            recipients: Override default recipients

        Returns:
            bool: True if email was sent successfully, False otherwise
        """
        try:
            # Use provided recipients or default
            email_recipients = recipients or self.recipients

            # Validate recipients
            valid_recipients = self._validate_recipients(email_recipients)

            # Validate credentials
            if not self.sender_email or not self.sender_password:
                self.logger.error("Email credentials not configured")
                return False

            # Create email content
            subject = f"[WAKALAT-{severity.value}] {alert_type.value}: {title}"
            body = self._create_email_body(
                alert_type=alert_type,
                severity=severity,
                title=title,
                message=message,
                context=context,
                exception=exception
            )

            # Send email
            success = self._send_email(subject, body, valid_recipients)

            if success:
                self.logger.info(f"Alert sent successfully: {alert_type.value} - {title}")
            else:
                self.logger.error(f"Failed to send alert: {alert_type.value} - {title}")

            return success

        except Exception as e:
            self.logger.error(f"Error in send_alert: {str(e)}")
            return False

    def _create_email_body(self,
                           alert_type: AlertType,
                           severity: AlertSeverity,
                           title: str,
                           message: str,
                           context: Optional[Dict[str, Any]] = None,
                           exception: Optional[Exception] = None) -> str:
        """Create formatted email body."""

        # Get severity emoji
        severity_emoji = {
            AlertSeverity.LOW: "🟡",
            AlertSeverity.MEDIUM: "🟠",
            AlertSeverity.HIGH: "🔴",
            AlertSeverity.CRITICAL: "🚨"
        }.get(severity, "⚠️")

        body = f"""
{severity_emoji} WAKALAT SYSTEM ALERT {severity_emoji}

ALERT DETAILS:
==============
Type: {alert_type.value}
Severity: {severity.value}
Title: {title}
Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
Server: {socket.gethostname()}

DESCRIPTION:
============
{message}
"""

        # Add context information
        if context:
            try:
                context_str = json.dumps(context, indent=2, default=str, ensure_ascii=False)
                body += f"""

CONTEXT DATA:
=============
{context_str}
"""
            except Exception as e:
                body += f"""

CONTEXT DATA:
=============
Error serializing context: {str(e)}
Raw context: {str(context)}
"""

        # Add exception details
        if exception:
            body += f"""

EXCEPTION DETAILS:
==================
Type: {type(exception).__name__}
Message: {str(exception)}

TRACEBACK:
==========
{traceback.format_exc()}
"""

        # Add system information
        try:
            import platform
            python_version = platform.python_version()
            system_info = platform.platform()
        except Exception:
            python_version = "Unknown"
            system_info = "Unknown"

        body += f"""

SYSTEM INFO:
============
Server: Wakalat Document Retrieval System
Environment: {os.getenv('ENVIRONMENT', 'Unknown')}
Python Version: {python_version}
Platform: {system_info}
Version: 1.0.0

RECOMMENDED ACTIONS:
===================
"""

        # Add severity-specific recommendations
        if severity == AlertSeverity.CRITICAL:
            body += """
1. Immediate investigation required
2. Check system logs for related errors
3. Verify database and network connectivity
4. Consider enabling fallback mechanisms
"""
        elif severity == AlertSeverity.HIGH:
            body += """
1. Investigation required within 1 hour
2. Monitor system for related issues
3. Check recent deployments or changes
"""
        elif severity == AlertSeverity.MEDIUM:
            body += """
1. Investigation required within 4 hours
2. Review system metrics and logs
3. Consider preventive measures
"""
        else:
            body += """
1. Investigation can be scheduled
2. Monitor for pattern of similar issues
"""

        body += """
---
This is an automated alert from the Wakalat Document Retrieval System.
Please investigate and take appropriate action.

For urgent issues, contact the on-call engineer.
"""

        return body

    def _send_email(self, subject: str, body: str, recipients: List[str]) -> bool:
        """Send email using SMTP with robust error handling."""
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.sender_email
            msg['To'] = ', '.join(recipients)
            msg['Subject'] = subject

            # Add plain text body
            text_part = MIMEText(body, 'plain', 'utf-8')
            msg.attach(text_part)

            # Create HTML version with better formatting
            html_body = self._create_html_body(body)
            html_part = MIMEText(html_body, 'html', 'utf-8')
            msg.attach(html_part)

            # Send email using context manager
            with self._smtp_connection() as server:
                # Set debug level if needed (handle custom logger safely)
                try:
                    if hasattr(self.logger, 'level') and self.logger.level <= logging.DEBUG:
                        server.set_debuglevel(1)
                except AttributeError:
                    # Custom logger doesn't have level attribute, skip debug setting
                    pass

                server.sendmail(self.sender_email, recipients, msg.as_string())

            return True

        except EmailConnectionError as e:
            self.logger.error(f"Email connection error: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to send email: {str(e)}")
            return False

    def _create_html_body(self, plain_text: str) -> str:
        """Convert plain text body to HTML with better formatting."""
        import html

        # Escape HTML characters
        escaped_text = html.escape(plain_text)

        # Convert to HTML with proper formatting
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: 'Courier New', monospace; margin: 20px; }}
        .alert-header {{ background-color: #ff6b6b; color: white; padding: 15px; text-align: center; }}
        .alert-content {{ background-color: #f8f9fa; padding: 20px; border: 1px solid #dee2e6; }}
        .section {{ margin-bottom: 20px; }}
        .section-title {{ font-weight: bold; color: #495057; border-bottom: 1px solid #ccc; }}
        pre {{ background-color: #f1f3f4; padding: 10px; overflow-x: auto; }}
    </style>
</head>
<body>
    <div class="alert-header">
        <h2>🚨 WAKALAT SYSTEM ALERT 🚨</h2>
    </div>
    <div class="alert-content">
        <pre>{escaped_text}</pre>
    </div>
</body>
</html>
"""
        return html_body

    # Convenience methods for common alert types (keeping same method names)

    def alert_document_retrieval_failure(self,
                                         year: int,
                                         page: int,
                                         url: str,
                                         error: Exception,
                                         context: Optional[Dict] = None) -> bool:
        """Alert for document retrieval failures."""
        return self.send_alert(
            alert_type=AlertType.DOCUMENT_RETRIEVAL_FAILURE,
            severity=AlertSeverity.MEDIUM,
            title=f"Failed to retrieve documents for year {year}, page {page}",
            message=f"Unable to retrieve documents from URL: {url}\n\n"
                    f"This may indicate:\n"
                    f"- Network connectivity issues\n"
                    f"- Website structure changes\n"
                    f"- Rate limiting or blocking\n"
                    f"- Server errors on target site\n\n"
                    f"Error: {str(error)}",
            context={
                "year": year,
                "page": page,
                "url": url,
                "error_type": type(error).__name__,
                **(context or {})
            },
            exception=error
        )

    def alert_document_id_extraction_failure(self,
                                             links_without_ids: List[str],
                                             year: int,
                                             page: int,
                                             context: Optional[Dict] = None) -> bool:
        """Alert for document ID extraction failures."""
        return self.send_alert(
            alert_type=AlertType.DOCUMENT_ID_EXTRACTION_FAILURE,
            severity=AlertSeverity.HIGH,
            title=f"Failed to extract document IDs for {len(links_without_ids)} links",
            message=f"Unable to extract document IDs from {len(links_without_ids)} links "
                    f"for year {year}, page {page}\n\n"
                    f"This may indicate:\n"
                    f"- Website URL structure changes\n"
                    f"- Regex pattern needs updating\n"
                    f"- Malformed URLs in response\n\n"
                    f"Sample problematic links:\n" +
                    "\n".join(f"  - {link}" for link in links_without_ids[:5]),
            context={
                "year": year,
                "page": page,
                "failed_links_count": len(links_without_ids),
                "sample_links": links_without_ids[:10],  # First 10 for debugging
                **(context or {})
            }
        )

    def alert_bigquery_failure(self,
                               operation: str,
                               error: Exception,
                               data_context: Optional[Dict] = None) -> bool:
        """Alert for BigQuery operation failures."""
        return self.send_alert(
            alert_type=AlertType.BIGQUERY_FAILURE,
            severity=AlertSeverity.CRITICAL,
            title=f"BigQuery {operation} operation failed",
            message=f"BigQuery operation '{operation}' failed\n\n"
                    f"This may indicate:\n"
                    f"- Authentication/permission issues\n"
                    f"- Network connectivity problems\n"
                    f"- Table schema mismatches\n"
                    f"- Data validation errors\n"
                    f"- Quota exceeded\n"
                    f"- Service outage\n\n"
                    f"Immediate action required to prevent data loss.\n\n"
                    f"Error: {str(error)}",
            context={
                "operation": operation,
                "error_type": type(error).__name__,
                "table_info": data_context.get("table_info") if data_context else None,
                **(data_context or {})
            },
            exception=error
        )

    def alert_data_validation_failure(self,
                                      validation_errors: List[str],
                                      data_sample: Optional[Dict] = None,
                                      context: Optional[Dict] = None) -> bool:
        """Alert for data validation failures."""
        return self.send_alert(
            alert_type=AlertType.DATA_VALIDATION_FAILURE,
            severity=AlertSeverity.MEDIUM,
            title=f"Data validation failed with {len(validation_errors)} errors",
            message=f"Data validation failed with the following errors:\n\n" +
                    "\n".join(f"  - {error}" for error in validation_errors[:10]) +
                    (f"\n  ... and {len(validation_errors) - 10} more errors"
                     if len(validation_errors) > 10 else "") +
                    "\n\nThis may indicate:\n"
                    "- Data source format changes\n"
                    "- Schema mismatches\n"
                    "- Data corruption\n"
                    "- Validation rules need updating",
            context={
                "validation_errors": validation_errors,
                "error_count": len(validation_errors),
                "data_sample": data_sample,
                **(context or {})
            }
        )

    def alert_rate_limit_exceeded(self,
                                  service: str,
                                  retry_after: Optional[int] = None,
                                  context: Optional[Dict] = None) -> bool:
        """Alert for rate limit exceeded."""
        return self.send_alert(
            alert_type=AlertType.RATE_LIMIT_EXCEEDED,
            severity=AlertSeverity.MEDIUM,
            title=f"Rate limit exceeded for {service}",
            message=f"Rate limit exceeded for service: {service}\n\n"
                    f"{'Retry after: ' + str(retry_after) + ' seconds' if retry_after else 'No retry info available'}\n\n"
                    f"Consider:\n"
                    f"- Increasing delays between requests\n"
                    f"- Implementing exponential backoff\n"
                    f"- Checking service quotas\n"
                    f"- Using request queuing\n"
                    f"- Distributing load across multiple accounts/keys",
            context={
                "service": service,
                "retry_after": retry_after,
                "timestamp": datetime.now().isoformat(),
                **(context or {})
            }
        )

    def alert_system_error(self,
                           component: str,
                           error: Exception,
                           context: Optional[Dict] = None) -> bool:
        """Alert for general system errors."""
        return self.send_alert(
            alert_type=AlertType.SYSTEM_ERROR,
            severity=AlertSeverity.HIGH,
            title=f"System error in {component}",
            message=f"Unexpected system error occurred in component: {component}\n\n"
                    f"Error: {str(error)}\n\n"
                    f"This may indicate:\n"
                    f"- Code bugs or logic errors\n"
                    f"- Resource exhaustion\n"
                    f"- External dependency failures\n"
                    f"- Configuration issues",
            context={
                "component": component,
                "error_type": type(error).__name__,
                **(context or {})
            },
            exception=error
        )

    def test_alert_system(self) -> bool:
        """Send a test alert to verify the system is working."""
        return self.send_alert(
            alert_type=AlertType.SYSTEM_ERROR,
            severity=AlertSeverity.LOW,
            title="Alert System Test",
            message="This is a test alert to verify the alert system is functioning correctly.\n\n"
                    "If you receive this message, the alert system is properly configured.",
            context={
                "test": True,
                "timestamp": datetime.now().isoformat(),
                "smtp_server": self.smtp_server,
                "smtp_port": self.smtp_port
            }
        )


# Singleton instance for easy access
_alert_system_instance: Optional[WakalatAlertSystem] = None


def get_alert_system() -> WakalatAlertSystem:
    """Get or create the global alert system instance."""
    global _alert_system_instance
    if _alert_system_instance is None:
        _alert_system_instance = WakalatAlertSystem()
    return _alert_system_instance


# Convenience functions for quick access (keeping same function names)
def send_alert(*args, **kwargs) -> bool:
    """Send an alert using the global alert system."""
    return get_alert_system().send_alert(*args, **kwargs)


def alert_document_retrieval_failure(*args, **kwargs) -> bool:
    """Send document retrieval failure alert."""
    return get_alert_system().alert_document_retrieval_failure(*args, **kwargs)


def alert_document_id_extraction_failure(*args, **kwargs) -> bool:
    """Send document ID extraction failure alert."""
    return get_alert_system().alert_document_id_extraction_failure(*args, **kwargs)


def alert_bigquery_failure(*args, **kwargs) -> bool:
    """Send BigQuery failure alert."""
    return get_alert_system().alert_bigquery_failure(*args, **kwargs)


def alert_data_validation_failure(*args, **kwargs) -> bool:
    """Send data validation failure alert."""
    return get_alert_system().alert_data_validation_failure(*args, **kwargs)


def alert_rate_limit_exceeded(*args, **kwargs) -> bool:
    """Send rate limit exceeded alert."""
    return get_alert_system().alert_rate_limit_exceeded(*args, **kwargs)


def alert_system_error(*args, **kwargs) -> bool:
    """Send system error alert."""
    return get_alert_system().alert_system_error(*args, **kwargs)