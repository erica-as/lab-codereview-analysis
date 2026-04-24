import csv
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from dotenv import load_dotenv
from github_client import GitHubClient

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
DATA_DIR = os.getenv("DATA_DIR", "./data")
OUTPUT_CSV = os.getenv("OUTPUT_CSV", "pull_requests_data.csv")
REPOSITORIES_CSV = os.getenv("REPOSITORIES_CSV", "selected_repositories.csv")
LOG_FILE = os.getenv("LOG_FILE", "./data/crawler.log")
GITHUB_CONCURRENCY = max(1, int(os.getenv("GITHUB_CONCURRENCY", "16")))

TARGET_REPO_COUNT = 200
MIN_CLOSED_PRS = 100
# Search /repositories: máx. 10 páginas × 100 = 1000 resultados
MAX_SEARCH_PAGES = 10
GITHUB_API_BASE = "https://api.github.com"

os.makedirs(DATA_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

_log_lock = threading.Lock()


def _tlog(msg: str) -> None:
    with _log_lock:
        logger.info(msg)


class GitHubCrawler:
    def __init__(self) -> None:
        if not GITHUB_TOKEN:
            logger.warning(
                "Token do GitHub não encontrado. As requisições da API podem ser limitadas."
            )
        self.client = GitHubClient(GITHUB_TOKEN or "")

    def get_popular_repositories(self, limit: int = TARGET_REPO_COUNT) -> List[Dict[str, Any]]:
        """Pagina a search/repositories até preencher `limit` repositórios com ≥ MIN_CLOSED_PRS PRs fechados."""
        _tlog(
            f"Buscando {limit} repositórios (popularidade) com pelo menos {MIN_CLOSED_PRS} PRs fechados…"
        )

        url = f"{GITHUB_API_BASE}/search/repositories"
        base_params: Dict[str, Any] = {
            "q": "stars:>100 sort:stars",
            "sort": "stars",
            "order": "desc",
        }

        selected: List[Dict[str, Any]] = []
        search_page = 1

        while len(selected) < limit and search_page <= MAX_SEARCH_PAGES:
            params = {**base_params, "per_page": 100, "page": search_page}
            r = self.client.get(url, params=params)
            if r.status_code != 200:
                _tlog(
                    f"Falha na busca de repositórios pág. {search_page}: {r.status_code} {r.text[:200]}"
                )
                break
            data = r.json()
            items = data.get("items") or []
            if not items:
                break

            for repo in items:
                if len(selected) >= limit:
                    break
                fn = repo.get("full_name", "")
                prs = self._get_repository_pr_count(fn)
                _tlog(
                    f"Verificando {fn}: {repo.get('stargazers_count', 0)} estrelas, "
                    f"{prs} PRs fechados (search)"
                )
                if prs >= MIN_CLOSED_PRS:
                    repo["pr_count"] = prs
                    selected.append(repo)
                    _tlog(f"✓ Selecionado ({len(selected)}/{limit}): {fn} ({prs} PRs)")

            if len(items) < 100:
                break
            search_page += 1

        if len(selected) < limit:
            _tlog(
                f"AVISO: Apenas {len(selected)} repositórios com ≥{MIN_CLOSED_PRS} PRs fechados "
                f"foram encontrados (máx. {MAX_SEARCH_PAGES * 100} candidatos via search)."
            )
        return selected

    def _get_repository_pr_count(self, repo_full_name: str) -> int:
        """Total de PRs fechados (inclui merged), via search/issues."""
        url = f"{GITHUB_API_BASE}/search/issues"
        params = {
            "q": f"repo:{repo_full_name} type:pr is:closed",
            "per_page": 1,
        }
        r = self.client.get(url, params=params)
        if r.status_code != 200:
            return 0
        return int(r.json().get("total_count", 0))

    def get_pull_requests(self, repo_full_name: str) -> List[Dict[str, Any]]:
        _tlog(f"Buscando PRs fechados de {repo_full_name}…")
        url = f"{GITHUB_API_BASE}/repos/{repo_full_name}/pulls"
        params: Dict[str, Any] = {"state": "closed", "per_page": 100}
        prs = self.client.get_list_paginated(url, params, max_pages=100)

        out: List[Dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=GITHUB_CONCURRENCY) as ex:
            futs = {
                ex.submit(self._process_pr, repo_full_name, pr): pr
                for pr in prs
            }
            for fut in as_completed(futs):
                try:
                    row = fut.result()
                    if row:
                        out.append(row)
                except Exception as e:  # noqa: BLE001
                    _tlog(f"Erro ao processar PR em {repo_full_name}: {e}")
        out.sort(key=lambda r: int(r.get("number", 0) or 0))
        _tlog(f"Selecionados {len(out)} PRs (critério enunciado) de {repo_full_name}")
        return out

    def _process_pr(
        self, repo_full_name: str, pr: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Filtra e extrai métricas; compõe dados de vários endpoints."""
        state = (pr.get("state") or "").lower()
        merged = bool(pr.get("merged_at"))
        if not merged and state != "closed":
            return None

        created_at = datetime.fromisoformat(
            str(pr["created_at"]).replace("Z", "+00:00")
        )
        closed_at_str = pr.get("merged_at") or pr.get("closed_at")
        if not closed_at_str:
            return None
        closed_at = datetime.fromisoformat(
            str(closed_at_str).replace("Z", "+00:00")
        )
        if closed_at - created_at < timedelta(hours=1):
            return None

        owner, repo = repo_full_name.split("/", 1)
        num = pr["number"]
        base = f"{GITHUB_API_BASE}/repos/{owner}/{repo}"

        review_objs = self.client.get_list_paginated(
            f"{base}/pulls/{num}/reviews",
            {},
            max_pages=20,
        )
        n_submitted_reviews = len(review_objs)
        if n_submitted_reviews < 1:
            return None

        pr_detail = self.client.get_json(f"{base}/pulls/{num}")
        if not pr_detail:
            return None

        issue_comments = self.client.get_list_paginated(
            f"{base}/issues/{num}/comments",
            {},
            max_pages=20,
        )
        line_comments = self.client.get_list_paginated(
            f"{base}/pulls/{num}/comments",
            {},
            max_pages=20,
        )

        body = (pr_detail.get("body") or "") or ""
        body_chars = len(body)

        pr_author = (pr.get("user") or {}).get("login") or ""
        participants = self._unique_participant_count(
            pr_author, review_objs, issue_comments, line_comments
        )

        comments_count = int(pr.get("comments") or 0)
        review_comments_count = int(pr.get("review_comments") or 0)
        add = int(pr_detail.get("additions") or 0)
        dele = int(pr_detail.get("deletions") or 0)

        analysis_time_hours = (closed_at - created_at).total_seconds() / 3600.0
        metrics = {
            "files_changed": int(pr_detail.get("changed_files") or 0),
            "lines_added": add,
            "lines_deleted": dele,
            "total_changes": add + dele,
            "analysis_time_hours": round(analysis_time_hours, 2),
            "created_at": pr["created_at"],
            "closed_at": closed_at_str,
            "description_chars": body_chars,
            "has_description": body_chars > 0,
            "participants": participants,
            "comments_count": comments_count,
            "review_comments_count": review_comments_count,
            "total_interactions": comments_count + review_comments_count,
            "merged": merged,
            "review_count": n_submitted_reviews,
        }
        return {**pr, "metrics": metrics, "repository": repo_full_name}

    @staticmethod
    def _unique_participant_count(
        author: str,
        reviews: List[Dict[str, Any]],
        issue_comments: List[Dict[str, Any]],
        line_comments: List[Dict[str, Any]],
    ) -> int:
        logins: Set[str] = set()
        if author:
            logins.add(author)
        for r in reviews:
            u = (r.get("user") or {}).get("login")
            if u:
                logins.add(u)
        for c in issue_comments + line_comments:
            u = (c.get("user") or {}).get("login")
            if u:
                logins.add(u)
        return len(logins)

    def save_repositories_to_csv(self, repos: List[Dict[str, Any]]) -> str:
        output_path = os.path.join(DATA_DIR, REPOSITORIES_CSV)
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "name",
                    "owner",
                    "full_name",
                    "description",
                    "stars",
                    "forks",
                    "open_issues",
                    "pr_count",
                    "primary_language",
                    "created_at",
                    "updated_at",
                ]
            )
            for repo in repos:
                writer.writerow(
                    [
                        repo.get("name", ""),
                        (repo.get("owner") or {}).get("login", ""),
                        repo.get("full_name", ""),
                        repo.get("description", ""),
                        repo.get("stargazers_count", 0),
                        repo.get("forks_count", 0),
                        repo.get("open_issues_count", 0),
                        repo.get("pr_count", 0),
                        repo.get("language", ""),
                        repo.get("created_at", ""),
                        repo.get("updated_at", ""),
                    ]
                )
        _tlog(f"Salvos {len(repos)} repositórios em {output_path}")
        return output_path

    def save_prs_to_csv(self, prs: List[Dict[str, Any]]) -> str:
        output_path = os.path.join(DATA_DIR, OUTPUT_CSV)
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "repository",
                    "pr_number",
                    "pr_title",
                    "pr_author",
                    "created_at",
                    "closed_at",
                    "merged",
                    "files_changed",
                    "lines_added",
                    "lines_deleted",
                    "total_changes",
                    "analysis_time_hours",
                    "description_chars",
                    "has_description",
                    "participants",
                    "comments_count",
                    "review_comments_count",
                    "total_interactions",
                    "review_count",
                ]
            )
            for pr in prs:
                m = pr.get("metrics", {})
                writer.writerow(
                    [
                        pr.get("repository", ""),
                        pr.get("number", ""),
                        pr.get("title", ""),
                        (pr.get("user") or {}).get("login", ""),
                        pr.get("created_at", ""),
                        m.get("closed_at", ""),
                        m.get("merged", False),
                        m.get("files_changed", 0),
                        m.get("lines_added", 0),
                        m.get("lines_deleted", 0),
                        m.get("total_changes", 0),
                        m.get("analysis_time_hours", 0),
                        m.get("description_chars", 0),
                        m.get("has_description", False),
                        m.get("participants", 0),
                        m.get("comments_count", 0),
                        m.get("review_comments_count", 0),
                        m.get("total_interactions", 0),
                        m.get("review_count", 0),
                    ]
                )
        _tlog(f"Salvos {len(prs)} PRs em {output_path}")
        return output_path

    def run(self) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        _tlog("=" * 80)
        _tlog("Iniciando coleta de dados de PRs do GitHub (Lab03S01)")
        _tlog(f"Concorrência: GITHUB_CONCURRENCY={GITHUB_CONCURRENCY}")
        _tlog("=" * 80)

        repos = self.get_popular_repositories(limit=TARGET_REPO_COUNT)
        self.save_repositories_to_csv(repos)

        all_prs: List[Dict[str, Any]] = []
        for i, repo in enumerate(repos, 1):
            _tlog(
                f"Processando repositório {i}/{len(repos)}: {repo['full_name']}"
            )
            all_prs.extend(self.get_pull_requests(repo["full_name"]))

        self.save_prs_to_csv(all_prs)
        _tlog("=" * 80)
        _tlog("Coleta concluída")
        _tlog(f"Total de repositórios: {len(repos)}")
        _tlog(f"Total de PRs coletados: {len(all_prs)}")
        _tlog("=" * 80)
        return repos, all_prs


def main() -> None:
    crawler = GitHubCrawler()
    crawler.run()


if __name__ == "__main__":
    main()
