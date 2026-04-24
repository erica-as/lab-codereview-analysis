# Lab Code Review Analysis - Lab03S01

## Descrição

Este laboratório coleta dados de Pull Requests (PRs) de repositórios populares no GitHub para análise de revisão de código. O projeto implementa a primeira etapa do Lab03 (Lab03S01) que compreende:

1. **Seleção de Repositórios**: até **200** repositórios extraídos da busca pública `sort:stars`, **paginando** a API até preencher essa quantidade com o filtro abaixo (máx. 1000 resultados de busca; se não forem 200, o log explica o déficit).
2. **Filtragem de Repositórios**: repositórios com pelo menos **100** PRs **fechados** (`is:closed` = merged + fechado sem merge).
3. **Coleta de PRs**: PRs que atendem aos critérios (ver secção seguinte), com **composição** de vários endpoints REST.
4. **Extração de Métricas**: tamanho, tempo de análise, descrição, interações, número de *reviews* oficiais.

## Critérios de Seleção de PRs

- Estado **MERGED** ou **CLOSED** (via API, `state=closed` e eventual `merged_at`).
- **Pelo menos 1** item na lista de [Pull request reviews](https://docs.github.com/en/rest/pulls/reviews#list-reviews-for-a-pull-request) (`GET /repos/{owner}/{repo}/pulls/{pull_number}/reviews`), não confundir só com comentários em linha ou de *issue*.
- **Tempo de análise** > **1 h** (entre criação e `merged_at` ou `closed_at`).

## Métricas e origem (REST v3)

| Métrica / coluna | Origem (composição) |
|------------------|----------------------|
| `files_changed`, `lines_*`, tamanho | `GET /repos/.../pulls/{n}` (PR completo) |
| `description_chars` | Corpo `body` do PR completo |
| `analysis_time_*`, `closed_at` | Timestamps do PR |
| `comments_count` | Campo `comments` do PR (comentários da *issue* do PR) |
| `review_comments_count` | Campo `review_comments` (comentários de revisão em diff) |
| `total_interactions` | `comments` + `review_comments` |
| `participants` | Conjunto único de *logins*: autor + comentadores em `/issues/{n}/comments` e `/pulls/{n}/comments` + autores de `/pulls/{n}/reviews` |
| `review_count` | Nº de entradas devolvidas por `/pulls/{n}/reviews` (submissões de *review*) |

Processamento de PRs usa `ThreadPoolExecutor` com tamanho `GITHUB_CONCURRENCY`; [`github_client`](src/github_client.py) usa **uma `Session` por *thread*** para I/O em paralelo (com *lock* só na pausa global de *rate limit*). As linhas de `pull_requests_data.csv` por repositório ficam **ordenadas por `pr_number`**. A API continua a ser o gargalo; 403/abuso: reduzir `GITHUB_CONCURRENCY`.

## Configuração

### 1. Instalação de Dependências

```bash
pip install -r requirements.txt
```

### 2. Variáveis de ambiente

```bash
cp .env.example .env
```

Edite [`.env`](.env) e preencha `GITHUB_TOKEN` (e opcionalmente `GITHUB_CONCURRENCY`):

```env
GITHUB_TOKEN=ghp_xxxxxxxx
DATA_DIR=./data
OUTPUT_CSV=pull_requests_data.csv
REPOSITORIES_CSV=selected_repositories.csv
LOG_FILE=./data/crawler.log
GITHUB_CONCURRENCY=16
```

Para gerar um token: https://github.com/settings/tokens (acesso a repositórios públicos, ex. `public_repo` em tokens clássicos).

## Execução

```bash
python src/crawler.py
```

1. Conecta à API (com *rate limit* e retentativas básicas em [`src/github_client.py`](src/github_client.py)).
2. Pagina `search/repositories` até 200 repositórios com ≥ 100 PRs fechados (ou esgota a busca).
3. Por repositório, obtém PRs `closed` e, em paralelo, compõe métricas por PR.
4. Gera `data/selected_repositories.csv` e `data/pull_requests_data.csv` e `data/crawler.log`.

## Documentação adicional (enunciado)

- [docs/enunciado.md](docs/enunciado.md) — enunciado em Markdown  
- [docs/checklist_enunciado.txt](docs/checklist_enunciado.txt) — sugestão de estrutura de relatório  
- PDF do laboratório em `docs/` (se entregue no repositório)

## Saída

Ficheiros em `data/` (não versionados por defeito; ver [`.gitignore`](.gitignore)):

- **`selected_repositories.csv`**: repositórios selecionados.  
- **`pull_requests_data.csv`**: uma linha por PR que passou nos filtros (por repositório, linhas ordenadas por número do PR).  
- **`crawler.log`**: log de execução.

## Estrutura do Projeto

```
lab-codereview-analysis/
├── src/
│   ├── crawler.py         # Orquestração, filtros, CSV, paralelismo
│   └── github_client.py  # Sessão HTTP, paginação, *rate limit*
├── docs/                   # Enunciado e checklists
├── data/                   # Saída (gerada, ignorada no Git)
├── requirements.txt
├── .env.example
├── .env                    # Não versionar
└── README.md
```
