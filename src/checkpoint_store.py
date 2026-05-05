import json
import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List


class CheckpointStore:
    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        self._lock = threading.Lock()
        self._state: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        if not os.path.exists(self.file_path):
            return {"repos": {}}
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    return {"repos": {}}
                if "repos" not in data or not isinstance(data["repos"], dict):
                    data["repos"] = {}
                return data
        except (json.JSONDecodeError, OSError):
            return {"repos": {}}

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.file_path) or ".", exist_ok=True)
        tmp_path = f"{self.file_path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(self._state, f, ensure_ascii=True, indent=2, sort_keys=True)
        os.replace(tmp_path, self.file_path)

    def get_repo_state(self, repo_full_name: str) -> Dict[str, Any]:
        with self._lock:
            data = (self._state.get("repos") or {}).get(repo_full_name) or {}
            return {
                "status": str(data.get("status") or "pending"),
                "next_page": int(data.get("next_page") or 1),
                "eligible_count": int(data.get("eligible_count") or 0),
                "exhausted": bool(data.get("exhausted") or False),
                "error": str(data.get("error") or ""),
                "updated_at": str(data.get("updated_at") or ""),
            }

    def get_all_done_repos(self) -> List[str]:
        """Retorna lista de repositórios com status='done'."""
        with self._lock:
            return [
                name for name, data in (self._state.get("repos") or {}).items()
                if data.get("status") == "done"
            ]

    def update_repo_state(
        self,
        repo_full_name: str,
        *,
        status: str,
        next_page: int,
        eligible_count: int,
        exhausted: bool = False,
        error: str = "",
    ) -> None:
        with self._lock:
            repos = self._state.setdefault("repos", {})
            repos[repo_full_name] = {
                "status": status,
                "next_page": int(next_page),
                "eligible_count": int(eligible_count),
                "exhausted": bool(exhausted),
                "error": error,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            self._save()
