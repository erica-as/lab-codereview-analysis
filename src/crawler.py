import os
import csv
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import requests
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
DATA_DIR = os.getenv('DATA_DIR', './data')
OUTPUT_CSV = os.getenv('OUTPUT_CSV', 'pull_requests_data.csv')
REPOSITORIES_CSV = os.getenv('REPOSITORIES_CSV', 'selected_repositories.csv')
LOG_FILE = os.getenv('LOG_FILE', './data/crawler.log')

GITHUB_API_BASE = 'https://api.github.com'
GITHUB_HEADERS = {
    'Accept': 'application/vnd.github.v3+json',
    'Authorization': f'token {GITHUB_TOKEN}' if GITHUB_TOKEN else ''
}

os.makedirs(DATA_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class GitHubCrawler:

    def __init__(self):
        if not GITHUB_TOKEN:
            logger.warning('Token do GitHub não encontrado. As requisições da API podem ser limitadas.')
        self.session = requests.Session()
        self.session.headers.update(GITHUB_HEADERS)
        self.rate_limit_remaining = None
        self.rate_limit_reset = None

    def _handle_rate_limit(self, response: requests.Response) -> None:
        self.rate_limit_remaining = int(response.headers.get('X-RateLimit-Remaining', 0))
        self.rate_limit_reset = int(response.headers.get('X-RateLimit-Reset', 0))

        if self.rate_limit_remaining < 100:
            reset_time = datetime.fromtimestamp(self.rate_limit_reset)
            logger.warning(
                f'Limite de requisições baixo: {self.rate_limit_remaining} requisições restantes. '
                f'Reinicia em {reset_time}'
            )

    def _make_request(self, url: str, params: Optional[Dict] = None) -> Optional[Dict]:
        try:
            response = self.session.get(url, params=params, timeout=10)
            self._handle_rate_limit(response)

            if response.status_code == 403:
                logger.error(f'Acesso proibido (403): {response.text}')
                return None
            elif response.status_code == 404:
                logger.debug(f'Não encontrado (404): {url}')
                return None
            elif response.status_code != 200:
                logger.error(f'Erro {response.status_code}: {response.text}')
                return None

            return response.json()
        except requests.RequestException as e:
            logger.error(f'Falha na requisição para {url}: {e}')
            return None

    def _paginate_requests(self, url: str, params: Optional[Dict] = None, max_pages: int = 100) -> List[Dict]:
        results = []
        page = 1

        while page <= max_pages:
            if not params:
                params = {}
            params['page'] = page
            params['per_page'] = 100

            data = self._make_request(url, params)
            if not data:
                break

            if isinstance(data, list):
                results.extend(data)
                if len(data) < 100: 
                    break
            else:
                results.append(data)
                break

            page += 1

        return results

    def get_popular_repositories(self, limit: int = 200) -> List[Dict]:
        logger.info(f'Buscando os {limit} repositórios mais populares...')

        url = f'{GITHUB_API_BASE}/search/repositories'
        params = {
            'q': 'stars:>100 sort:stars',
            'sort': 'stars',
            'order': 'desc',
            'per_page': 100
        }

        all_repos = []
        page = 1

        while len(all_repos) < limit:
            params['page'] = page
            response = self.session.get(url, params=params, timeout=10)
            self._handle_rate_limit(response)

            if response.status_code != 200:
                logger.error(f'Falha ao buscar repositórios: {response.status_code}')
                break

            data = response.json()
            if 'items' not in data or not data['items']:
                break

            all_repos.extend(data['items'])
            page += 1

        selected_repos = []
        for repo in all_repos[:limit]:
            if len(selected_repos) >= limit:
                break

            pr_count = repo.get('open_issues_count', 0)  
            logger.info(
                f"Verificando {repo['full_name']}: "
                f"{repo['stargazers_count']} estrelas, ~{pr_count} issues/PRs"
            )

            # Get actual PR count
            prs = self._get_repository_pr_count(repo['full_name'])
            if prs >= 100:
                repo['pr_count'] = prs
                selected_repos.append(repo)
                logger.info(f"✓ Selecionado: {repo['full_name']} ({prs} PRs)")
            else:
                logger.debug(f"✗ Ignorado: {repo['full_name']} ({prs} PRs)")

        logger.info(f'Selecionados {len(selected_repos)} repositórios com >= 100 PRs')
        return selected_repos

    def _get_repository_pr_count(self, repo_full_name: str) -> int:
        url = f'{GITHUB_API_BASE}/search/issues'
        params = {
            'q': f'repo:{repo_full_name} type:pr is:closed',
            'per_page': 1
        }

        response = self.session.get(url, params=params, timeout=10)
        self._handle_rate_limit(response)

        if response.status_code != 200:
            return 0

        data = response.json()
        return data.get('total_count', 0)

    def get_pull_requests(self, repo_full_name: str) -> List[Dict]:
        logger.info(f'Buscando PRs de {repo_full_name}...')

        url = f'{GITHUB_API_BASE}/repos/{repo_full_name}/pulls'
        params = {
            'state': 'closed',
            'per_page': 100
        }

        prs = self._paginate_requests(url, params, max_pages=50)
        logger.info(f'Encontrados {len(prs)} PRs fechados em {repo_full_name}')

        filtered_prs = []
        for pr in prs:
            if self._validate_pr(pr, repo_full_name):
                metrics = self._extract_metrics(pr, repo_full_name)
                if metrics:
                    filtered_prs.append({
                        **pr,
                        'metrics': metrics,
                        'repository': repo_full_name
                    })

        logger.info(f'Selecionados {len(filtered_prs)} PRs de {repo_full_name}')
        return filtered_prs

    def _validate_pr(self, pr: Dict, repo_full_name: str) -> bool:
        if not pr.get('merged_at') and pr.get('state') != 'closed':
            return False

        review_count = pr.get('review_comments', 0) + pr.get('comments', 0)
        if review_count < 1:
            return False

        created_at = datetime.fromisoformat(pr['created_at'].replace('Z', '+00:00'))
        closed_at_str = pr.get('merged_at') or pr.get('closed_at')
        if not closed_at_str:
            return False

        closed_at = datetime.fromisoformat(closed_at_str.replace('Z', '+00:00'))
        time_diff = closed_at - created_at

        if time_diff < timedelta(hours=1):
            return False

        return True

    def _extract_metrics(self, pr: Dict, repo_full_name: str) -> Optional[Dict]:
        try:
            url = f'{GITHUB_API_BASE}/repos/{repo_full_name}/pulls/{pr["number"]}'
            pr_details = self._make_request(url)

            if not pr_details:
                logger.warning(f'Não foi possível obter detalhes para o PR {pr["number"]}')
                return None

            created_at = datetime.fromisoformat(pr['created_at'].replace('Z', '+00:00'))
            closed_at_str = pr.get('merged_at') or pr.get('closed_at')
            closed_at = datetime.fromisoformat(closed_at_str.replace('Z', '+00:00'))

            files_changed = pr_details.get('changed_files', 0)
            additions = pr_details.get('additions', 0)
            deletions = pr_details.get('deletions', 0)
            total_changes = additions + deletions

            analysis_time_hours = (closed_at - created_at).total_seconds() / 3600

            body = pr.get('body') or ''
            body_chars = len(body)

            participants_count = len(set([pr.get('user', {}).get('login')] + 
                                        [c.get('user', {}).get('login') for c in []]))
            comments_count = pr.get('comments', 0)
            review_comments_count = pr.get('review_comments', 0)

            participants = self._get_pr_participants(repo_full_name, pr['number'])

            metrics = {
                # Size
                'files_changed': files_changed,
                'lines_added': additions,
                'lines_deleted': deletions,
                'total_changes': total_changes,
                # Analysis time
                'analysis_time_hours': round(analysis_time_hours, 2),
                'created_at': pr['created_at'],
                'closed_at': closed_at_str,
                # Description
                'description_chars': body_chars,
                'has_description': body_chars > 0,
                # Interactions
                'participants': participants,
                'comments_count': comments_count,
                'review_comments_count': review_comments_count,
                'total_interactions': comments_count + review_comments_count,
                # Status
                'merged': bool(pr.get('merged_at')),
                'review_count': pr.get('review_comments', 0)
            }

            return metrics
        except Exception as e:
            logger.error(f'Erro ao extrair métricas para o PR {pr.get("number")}: {e}')
            return None

    def _get_pr_participants(self, repo_full_name: str, pr_number: int) -> int:
        url = f'{GITHUB_API_BASE}/repos/{repo_full_name}/pulls/{pr_number}/comments'
        params = {'per_page': 100}

        comments = self._paginate_requests(url, params, max_pages=10)
        participants = set()

        # Add PR author
        participants.add(f"PR_{pr_number}")  # Placeholder for PR author

        # Add commenters
        for comment in comments:
            if 'user' in comment and 'login' in comment['user']:
                participants.add(comment['user']['login'])

        return len(participants)

    def save_repositories_to_csv(self, repos: List[Dict]) -> str:
        output_path = os.path.join(DATA_DIR, REPOSITORIES_CSV)

        try:
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'name',
                    'owner',
                    'full_name',
                    'description',
                    'stars',
                    'forks',
                    'open_issues',
                    'pr_count',
                    'primary_language',
                    'created_at',
                    'updated_at'
                ])

                for repo in repos:
                    writer.writerow([
                        repo.get('name', ''),
                        repo.get('owner', {}).get('login', ''),
                        repo.get('full_name', ''),
                        repo.get('description', ''),
                        repo.get('stargazers_count', 0),
                        repo.get('forks_count', 0),
                        repo.get('open_issues_count', 0),
                        repo.get('pr_count', 0),
                        repo.get('language', ''),
                        repo.get('created_at', ''),
                        repo.get('updated_at', '')
                    ])

            logger.info(f'Salvos {len(repos)} repositórios em {output_path}')
            return output_path
        except Exception as e:
            logger.error(f'Erro ao salvar CSV de repositórios: {e}')
            raise

    def save_prs_to_csv(self, prs: List[Dict]) -> str:
        output_path = os.path.join(DATA_DIR, OUTPUT_CSV)

        try:
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'repository',
                    'pr_number',
                    'pr_title',
                    'pr_author',
                    'created_at',
                    'closed_at',
                    'merged',
                    'files_changed',
                    'lines_added',
                    'lines_deleted',
                    'total_changes',
                    'analysis_time_hours',
                    'description_chars',
                    'has_description',
                    'participants',
                    'comments_count',
                    'review_comments_count',
                    'total_interactions',
                    'review_count'
                ])

                for pr in prs:
                    metrics = pr.get('metrics', {})
                    writer.writerow([
                        pr.get('repository', ''),
                        pr.get('number', ''),
                        pr.get('title', ''),
                        pr.get('user', {}).get('login', ''),
                        pr.get('created_at', ''),
                        metrics.get('closed_at', ''),
                        metrics.get('merged', False),
                        metrics.get('files_changed', 0),
                        metrics.get('lines_added', 0),
                        metrics.get('lines_deleted', 0),
                        metrics.get('total_changes', 0),
                        metrics.get('analysis_time_hours', 0),
                        metrics.get('description_chars', 0),
                        metrics.get('has_description', False),
                        metrics.get('participants', 0),
                        metrics.get('comments_count', 0),
                        metrics.get('review_comments_count', 0),
                        metrics.get('total_interactions', 0),
                        metrics.get('review_count', 0)
                    ])

            logger.info(f'Salvos {len(prs)} PRs em {output_path}')
            return output_path
        except Exception as e:
            logger.error(f'Erro ao salvar CSV de PRs: {e}')
            raise

    def run(self) -> Tuple[List[Dict], List[Dict]]:
        try:
            logger.info('=' * 80)
            logger.info('Iniciando coleta de dados de PRs do GitHub')
            logger.info('=' * 80)

            repos = self.get_popular_repositories(limit=200)
            self.save_repositories_to_csv(repos)

            all_prs = []
            for i, repo in enumerate(repos, 1):
                logger.info(f'Processando repositório {i}/{len(repos)}: {repo["full_name"]}')
                prs = self.get_pull_requests(repo['full_name'])
                all_prs.extend(prs)

            self.save_prs_to_csv(all_prs)

            logger.info('=' * 80)
            logger.info(f'Coleta de dados concluída!')
            logger.info(f'Total de repositórios: {len(repos)}')
            logger.info(f'Total de PRs coletados: {len(all_prs)}')
            logger.info('=' * 80)

            return repos, all_prs
        except Exception as e:
            logger.error(f'Erro fatal durante coleta de dados: {e}', exc_info=True)
            raise


def main():
    crawler = GitHubCrawler()
    repos, prs = crawler.run()


if __name__ == '__main__':
    main()
