"""
Base Validator Classes

Provides common validation patterns and base classes for all validators.
Reduces duplication across validation modules.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum
import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class Severity(Enum):
    """Standard severity levels for validation issues"""
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass
class ValidationIssue:
    """
    Base class for validation issues/violations

    Attributes:
        severity: Issue severity level
        category: Category/type of issue
        message: Human-readable issue description
        ticker: Optional ticker if issue is security-specific
        current_value: Current value (optional)
        expected_value: Expected/threshold value (optional)
    """
    severity: Severity
    category: str
    message: str
    ticker: Optional[str] = None
    current_value: Optional[float] = None
    expected_value: Optional[float] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON export"""
        return {
            'severity': self.severity.value,
            'category': self.category,
            'message': self.message,
            'ticker': self.ticker,
            'current_value': self.current_value,
            'expected_value': self.expected_value
        }

    def is_critical(self) -> bool:
        """Check if issue is critical severity"""
        return self.severity == Severity.CRITICAL


@dataclass
class ValidationReport(ABC):
    """
    Abstract base class for validation reports

    All validators should extend this to provide consistent structure.
    """
    validation_date: str  # ISO format datetime string
    issues: List[ValidationIssue]

    @abstractmethod
    def is_valid(self) -> bool:
        """
        Determine if validation passed

        Returns:
            True if no critical issues, False otherwise
        """
        pass

    @abstractmethod
    def get_score(self) -> float:
        """
        Calculate validation score

        Returns:
            Score value (typically 0-100)
        """
        pass

    @abstractmethod
    def to_dict(self) -> Dict:
        """Convert report to dictionary for JSON export"""
        pass

    def has_critical_issues(self) -> bool:
        """Check if report contains any critical issues"""
        return any(issue.is_critical() for issue in self.issues)

    def get_issues_by_severity(self, severity: Severity) -> List[ValidationIssue]:
        """
        Get all issues matching specified severity level

        Args:
            severity: Severity level to filter by

        Returns:
            List of issues with matching severity
        """
        return [issue for issue in self.issues if issue.severity == severity]

    def get_issue_count(self, severity: Optional[Severity] = None) -> int:
        """
        Get count of issues, optionally filtered by severity

        Args:
            severity: Optional severity filter

        Returns:
            Count of matching issues
        """
        if severity is None:
            return len(self.issues)
        return len(self.get_issues_by_severity(severity))


class BaseValidator(ABC):
    """
    Abstract base validator

    All validators should extend this class to provide consistent
    interface and shared functionality.
    """

    def __init__(self, name: str = "BaseValidator"):
        """
        Initialize validator

        Args:
            name: Validator name for logging
        """
        self.name = name
        self.validation_timestamp = datetime.now().isoformat()

    @abstractmethod
    def validate(self, *args, **kwargs) -> ValidationReport:
        """
        Run validation and return report

        Must be implemented by subclasses.

        Returns:
            ValidationReport instance
        """
        pass

    def export_report(
        self,
        report: ValidationReport,
        filepath: Path,
        format: str = 'json'
    ) -> bool:
        """
        Export validation report to file

        Args:
            report: ValidationReport instance
            filepath: Output file path
            format: Output format ('json' or 'markdown')

        Returns:
            True if export successful, False otherwise
        """
        try:
            filepath = Path(filepath)
            filepath.parent.mkdir(parents=True, exist_ok=True)

            if format == 'json':
                with open(filepath, 'w') as f:
                    json.dump(report.to_dict(), f, indent=2)
            elif format == 'markdown':
                with open(filepath, 'w') as f:
                    f.write(self._report_to_markdown(report))
            else:
                logger.error(f"Unknown export format: {format}")
                return False

            logger.info(f"Exported {self.name} report to {filepath}")
            return True

        except Exception as e:
            logger.error(f"Failed to export report to {filepath}: {e}")
            return False

    def _report_to_markdown(self, report: ValidationReport) -> str:
        """
        Convert report to markdown format

        Can be overridden by subclasses for custom formatting.

        Args:
            report: ValidationReport instance

        Returns:
            Markdown-formatted string
        """
        lines = [
            f"# Validation Report",
            f"\n**Validation Date:** {report.validation_date}",
            f"\n**Valid:** {'✅ Yes' if report.is_valid() else '❌ No'}",
            f"\n**Score:** {report.get_score():.1f}/100",
            f"\n## Issues ({len(report.issues)} total)",
        ]

        if not report.issues:
            lines.append("\n✅ No issues found")
        else:
            for severity in [Severity.CRITICAL, Severity.WARNING, Severity.INFO]:
                severity_issues = report.get_issues_by_severity(severity)
                if severity_issues:
                    lines.append(f"\n### {severity.value} ({len(severity_issues)})")
                    for issue in severity_issues:
                        ticker_str = f" ({issue.ticker})" if issue.ticker else ""
                        lines.append(f"- **{issue.category}**{ticker_str}: {issue.message}")

        return "\n".join(lines)
