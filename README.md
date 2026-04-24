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

### Execução na DigitalOcean (Droplet)

1. **Crédito** — No [GitHub Student Pack](https://education.github.com/pack), reivindica o benefício **DigitalOcean** (quando disponível) e liga a tua conta DO.
2. **Droplet** — Cria uma VM **Ubuntu 22.04/24.04 LTS**, região à escolha, plano mínimo **Regular SSD** (ex. 1 vCPU / 1–2 GB RAM) ou superior se o dataset for muito grande; chave SSH da tua máquina.
3. **Rede** — *Firewall* DO: permite **TCP 22** (SSH) a partir do teu IP (ou tua VPN).
4. **Primeiro login** (no teu Mac):

   ```bash
   ssh root@IP_DO_DROPLET
   apt update && apt install -y python3-pip python3-venv git tmux
   ```

5. **Código e ambiente** (não comites o `.env`):

   ```bash
   git clone https://github.com/erica-as/lab-codereview-analysis.git
   cd lab-codereview-analysis
   cp .env.example .env
   nano .env   # GITHUB_TOKEN=ghp_...  (PAT com leitura a repos públicos)
   pip3 install -r requirements.txt
   ```

6. **Sessão longa** (se a ligação SSH cair, o processo continua):

   ```bash
   tmux new -s crawl
   python3 src/crawler.py
   # Ctrl+B, depois D  →  desanexar
   # ssh de novo → tmux attach -t crawl
   ```

7. **Trazer os CSVs de volta** (no Mac, com o IP do Droplet):

   ```bash
   scp root@IP_DO_DROPLET:~/lab-codereview-analysis/data/pull_requests_data.csv .
   scp root@IP_DO_DROPLET:~/lab-codereview-analysis/data/crawler.log .
   ```

8. **Custo** — No painel DO, ativa **alertas de orçamento**; desliga ou destrói o Droplet quando acabares para não consumir o crédito após o *run*.

A API do GitHub continua com **rate limit**; o Droplet só evita depender do teu portátil.

### Execução no Azure (VM Linux)

Funciona de forma muito semelhante a um Droplet: uma **VM Ubuntu** com **SSH (porta 22)** aberta, mesmo fluxo de `git clone` → `.env` → `tmux` → `python3 src/crawler.py` → `scp` dos ficheiros de `data/`.

1. **Crédito** — [Azure for Students](https://azure.microsoft.com/free/students/) ou crédito normal; confirma no portal que tens subscrição ativa.
2. **Criar VM** — [Portal](https://portal.azure.com) → *Create a resource* → **Virtual machine**:
   - **Imagem:** Ubuntu Server **22.04/24.04 LTS**
   - **Tamanho:** qualquer *Burstable* mínimo (ex. B1s) basta; mais RAM alivia o Python se quiseres.
   - **Autenticação:** chave pública **SSH** (gere no portal ou usa `ssh-keygen` e cola a pública) — evita *password* só.
   - **Rede pública:** *Public IP* para SSH a partir do teu IP.
3. **NSG (firewall da VM)** — regra de entrada **TCP 22** a partir do teu IP (ou tua gama) — o *wizard* costuma abrir; se não SSHares, confirma *Network security group* → *Inbound* → 22.
4. **Ligar** (no teu Mac, com o *username* e IP públicos do portal):

   ```bash
   ssh azureuser@IP_PUBLICO_DA_VM
   # Se criaste com outro utilizador, substitui azureuser
   sudo apt update && sudo apt install -y python3-pip python3-venv git tmux
   ```

5. **Código e ambiente** — igual à secção DigitalOcean (passos 5 a 6 do Droplet: `git clone` → `cp .env.example .env` → `pip3 install -r requirements.txt` → `tmux` → `python3 src/crawler.py`). Ajusta o URL do `git clone` ao teu *fork* se for o caso.
6. **Trazer ficheiros** (no Mac):

   ```bash
   scp azureuser@IP_PUBLICO_DA_VM:~/lab-codereview-analysis/data/pull_requests_data.csv .
   scp azureuser@IP_PUBLICO_DA_VM:~/lab-codereview-analysis/data/crawler.log .
   ```

7. **Custo** — *Cost Management* no Azure para alertas. Quando acabar o *crawl*, **parar (deallocate)** ou apagar a VM para não pagar *compute* o tempo todo (disco/IPs podem ainda contar, conforme configuração).

O *rate limit* da API GitHub continua a ser o limite; a VM só corre o processo 24/7 sem depender do teu portátil.

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
