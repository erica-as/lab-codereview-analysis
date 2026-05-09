"""
Cliente HTTP para a API REST v3 do GitHub:
- uma requests.Session por thread (I/O paralelo seguro)
- pausa global coordenada quando a API reporta rate limit
- connection pooling para performance
"""
from __future__ import annotations

import logging
import random
import threading
import time
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class GitHubClient:
    def __init__(self, token: str, user_agent: str = "lab-codereview-analysis-crawler") -> None:
        self._token = token
        self._user_agent = user_agent
        self._headers: Dict[str, str] = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": user_agent,
        }
        if token:
            self._headers["Authorization"] = f"token {token}"

        self._local = threading.local()
        self._rate_limit_lock = threading.Lock()

    def _session(self) -> requests.Session:
        s = getattr(self._local, "session", None)
        if s is None:
            s = requests.Session()
            s.headers.update(self._headers)
            # Connection pooling - reuse connections
            adapter = HTTPAdapter(
                pool_connections=16,
                pool_maxsize=16,
                max_retries=Retry(total=0),  # handle retries ourselves
                pool_block=False,
            )
            s.mount("https://", adapter)
            s.mount("http://", adapter)
            self._local.session = s
        return s

    def request(
        self,
        method: str,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        timeout: int = 10,  # Reduced from 30s for faster failure detection
        max_retries: int = 2,  # Reduced - fail fast with concurrency
    ) -> requests.Response:
        for attempt in range(max_retries + 1):
            try:
                response = self._session().request(
                    method, url, params=params, timeout=timeout
                )
            except requests.exceptions.Timeout:
                wait = self._compute_backoff_seconds(attempt)
                logger.warning("Timeout de conexão em %s (tentativa %d/%d): aguardando %.2fs", url, attempt + 1, max_retries + 1, wait)
                time.sleep(wait)
                continue
            except requests.exceptions.ConnectionError as e:
                wait = self._compute_backoff_seconds(attempt)
                logger.warning("ConnectionError em %s (tentativa %d/%d): aguardando %.2fs — %s", url, attempt + 1, max_retries + 1, wait, e)
                time.sleep(wait)
                continue
            except requests.exceptions.RequestException as e:
                wait = self._compute_backoff_seconds(attempt)
                logger.warning("RequestException em %s (tentativa %d/%d): aguardando %.2fs — %s", url, attempt + 1, max_retries + 1, wait, e)
                time.sleep(wait)
                continue
            self._update_rate_from_headers(response)

            if response.status_code == 403 and (
                "rate limit" in (response.text or "").lower()
                or response.headers.get("X-RateLimit-Remaining") == "0"
            ):
                with self._rate_limit_lock:
                    self._sleep_for_rate_limit(response)
                continue

            if response.status_code in (403, 429):
                retry_after = self._parse_retry_after(response.headers.get("Retry-After"))
                if retry_after is not None:
                    logger.warning("Retry-After %ss em %s", retry_after, url)
                    with self._rate_limit_lock:
                        time.sleep(retry_after)
                    continue

                lower_text = (response.text or "").lower()
                if "abuse" in lower_text or "secondary rate limit" in lower_text:
                    wait = self._compute_backoff_seconds(attempt)
                    logger.warning("Abuse detection/secondary limit: aguardando %.2fs em %s", wait, url)
                    with self._rate_limit_lock:
                        time.sleep(wait)
                    continue

            if response.status_code in (502, 503, 504) and attempt < max_retries:
                time.sleep(self._compute_backoff_seconds(attempt))
                continue

            if response.status_code == 200 and hasattr(response, 'content') and not response.content and attempt < max_retries:
                time.sleep(self._compute_backoff_seconds(attempt))
                continue

            return response

        return response  # type: ignore[unreachable]

    def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: int = 30,
    ) -> requests.Response:
        return self.request("GET", url, params=params, timeout=timeout)

    def get_json(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        r = self.get(url, params=params)
        if r.status_code != 200:
            return None
        return r.json()

    def get_list_paginated(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        *,
        max_pages: int = 100,
        per_page: int = 100,
    ) -> List[Dict[str, Any]]:
        base: Dict[str, Any] = {} if not params else dict(params)
        out: List[Dict[str, Any]] = []
        page = 1
        while page <= max_pages:
            p = {**base, "page": page, "per_page": per_page}
            r = self.get(url, params=p)
            if r.status_code != 200:
                break
            chunk = r.json()
            if not isinstance(chunk, list) or not chunk:
                break
            out.extend(chunk)  # type: ignore[arg-type]
            if len(chunk) < per_page:
                break
            page += 1
        return out  # type: ignore[return-value]

    def _update_rate_from_headers(self, response: requests.Response) -> None:
        try:
            rem = response.headers.get("X-RateLimit-Remaining")
            if rem is not None and int(rem) <= 5 and int(rem) > 0:
                reset = response.headers.get("X-RateLimit-Reset")
                if reset:
                    from datetime import datetime

                    t = datetime.fromtimestamp(int(reset))
                    logger.info(
                        "API rate: %s restantes, reset em %s",
                        rem,
                        t,
                    )
        except (ValueError, TypeError):
            pass

    def _sleep_for_rate_limit(self, response: requests.Response) -> None:
        reset = response.headers.get("X-RateLimit-Reset")
        if not reset:
            time.sleep(60)
            return
        until = int(reset) - int(time.time()) + 1
        if until > 0:
            logger.warning("Limite de taxa: aguardando %s s", min(until, 3600))
            time.sleep(min(until, 3600))

    @staticmethod
    def _parse_retry_after(value: Optional[str]) -> Optional[int]:
        if value is None:
            return None
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None
        return max(1, min(parsed, 300))

    @staticmethod
    def _compute_backoff_seconds(attempt: int) -> float:
        base = min(float(2 ** attempt), 60.0)
        jitter = random.uniform(0.0, 1.0)
        return base + jitter
