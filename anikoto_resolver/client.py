"""
Resilient HTTP Client for Jikan and Anikoto requests.
"""

import time
import random
import requests
from typing import Optional, Dict, Any
from .exceptions import AnikotoAPIError, JikanAPIError

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/html, */*",
    "Referer": "https://anikoto.cz/",
}

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class HttpClient:
    """Handles HTTP requests with exponential backoff, rate-limit awareness, and retries."""
    
    def __init__(self, max_retries: int = 4, backoff_factor: float = 1.5, timeout: float = 12.0):
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    def get(self, url: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> requests.Response:
        last_error: Optional[str] = None
        req_headers = DEFAULT_HEADERS.copy()
        if headers:
            req_headers.update(headers)

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.get(url, params=params, headers=req_headers, timeout=self.timeout)
                if response.status_code not in RETRYABLE_STATUS_CODES:
                    return response
                
                # Check for Retry-After header
                retry_after = response.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    delay = float(retry_after)
                else:
                    jitter = random.uniform(0.1, 0.4)
                    delay = (self.backoff_factor * (2 ** (attempt - 1))) + jitter
                    
                last_error = f"HTTP {response.status_code}"
                if attempt < self.max_retries:
                    time.sleep(delay)

            except requests.RequestException as e:
                last_error = str(e)
                if attempt < self.max_retries:
                    time.sleep(self.backoff_factor * attempt)

        raise AnikotoAPIError(f"Request to '{url}' failed after {self.max_retries} attempts (last error: {last_error})")
