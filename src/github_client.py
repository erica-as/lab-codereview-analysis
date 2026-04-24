"""
Cliente HTTP para a API REST v3 do GitHub:
- uma requests.Session por thread (I/O paralelo seguro)
- pausa global coordenada quando a API reporta rate limit
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional

import requests

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
        # Uma thread de cada vez entra no sleep de rate limit (evita N× sleep em rajada)
        self._rate_limit_lock = threading.Lock()

    def _session(self) -> requests.Session:
        s = getattr(self._local, "session", None)
        if s is None:
            s = requests.Session()
            s.headers.update(self._headers)
            self._local.session = s
        return s

    def request(
        self,
        method: str,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        timeout: int = 30,
        max_retries: int = 3,
    ) -> requests.Response:
        for attempt in range(max_retries + 1):
            response = self._session().request(
                method, url, params=params, timeout=timeout
            )
            self._update_rate_from_headers(response)

            if response.status_code == 403 and (
                "rate limit" in (response.text or "").lower()
                or response.headers.get("X-RateLimit-Remaining") == "0"
            ):
                with self._rate_limit_lock:
                    self._sleep_for_rate_limit(response)
                continue

            if response.status_code in (403, 429) and response.headers.get("Retry-After"):
                wait = int(response.headers.get("Retry-After", 60))
                logger.warning("Retry-After %ss em %s", wait, url)
                with self._rate_limit_lock:
                    time.sleep(min(wait, 300))
                continue

            if response.status_code in (502, 503) and attempt < max_retries:
                time.sleep(1 + attempt)
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
            if rem is not None and int(rem) < 20:
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
