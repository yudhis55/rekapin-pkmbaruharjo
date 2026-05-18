"""Custom exceptions for the scraper."""
from __future__ import annotations


class ScraperError(Exception):
    """Base exception for all scraper errors."""


class LoginError(ScraperError):
    """Login failed (bad credentials, missing form elements, etc.)."""


class SelectorNotFoundError(ScraperError):
    """An expected selector was not found on the page."""


class SessionExpiredError(ScraperError):
    """Session expired - need to re-login."""


class RateLimitError(ScraperError):
    """EMR rate-limited or blocked us."""


class NavigationError(ScraperError):
    """Failed to navigate (wrong URL, missing element)."""


class FilterError(ScraperError):
    """Filter form interaction failed."""


class JobAlreadyRunningError(ScraperError):
    """Another scrape job is already active."""
