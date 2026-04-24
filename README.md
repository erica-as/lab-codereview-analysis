# Lab Code Review Analysis - Lab03S01

## Descrição

Este laboratório coleta dados de Pull Requests (PRs) de repositórios populares no GitHub para análise de revisão de código. O projeto implementa a primeira etapa do Lab03 (Lab03S01) que compreende:

1. **Seleção de Repositórios**: Identificação dos 200 repositórios mais populares do GitHub
2. **Filtragem de Repositórios**: Apenas repositórios com pelo menos 100 PRs (MERGED + CLOSED)
3. **Coleta de PRs**: Extração de PRs que atendem aos critérios específicos
4. **Extração de Métricas**: Coleta de métricas relacionadas ao tamanho, tempo de análise, descrição e interações

## Critérios de Seleção de PRs

Os PRs coletados devem atender aos seguintes critérios:

- Status: MERGED ou CLOSED
- Pelo menos 1 revisão (comentários/reviews)
- Tempo de análise > 1 hora (diferença entre criação e merge/close)

## Métricas Coletadas

Para cada PR, o script extrai as seguintes métricas:

### 1. **Tamanho (Size)**
- `files_changed`: Número de arquivos alterados
- `lines_added`: Total de linhas adicionadas
- `lines_deleted`: Total de linhas removidas
- `total_changes`: Total de linhas adicionadas + removidas

### 2. **Tempo de Análise (Analysis Time)**
- `analysis_time_hours`: Intervalo em horas entre criação e fechamento/merge
- `created_at`: Data/hora de criação do PR
- `closed_at`: Data/hora de fechamento/merge do PR

### 3. **Descrição (Description)**
- `description_chars`: Número de caracteres da descrição do PR
- `has_description`: Booleano indicando se há descrição

### 4. **Interações (Interactions)**
- `participants`: Número de participantes únicos na discussão
- `comments_count`: Número de comentários
- `review_comments_count`: Número de comentários de revisão
- `total_interactions`: Total de interações

### 5. **Status do PR**
- `merged`: Booleano indicando se foi feito merge
- `review_count`: Contagem de revisões

## Configuração

### 1. Instalação de Dependências

```bash
pip install -r requirements.txt
```

### 2. Configuração do GitHub Token

Crie um arquivo `.env` na raiz do projeto com seu token do GitHub:

```bash
cp .env.example .env
```

Edite o arquivo `.env` e adicione seu token do GitHub:

```
GITHUB_TOKEN=seu_token_github_aqui
DATA_DIR=./data
OUTPUT_CSV=pull_requests_data.csv
REPOSITORIES_CSV=selected_repositories.csv
LOG_FILE=./data/crawler.log
```

Para gerar um token do GitHub:
1. Vá para https://github.com/settings/tokens
2. Clique em "Generate new token"
3. Selecione as permissões necessárias (pelo menos `public_repo`)
4. Copie o token e adicione ao arquivo `.env`

## Execução

Para coletar os dados, execute:

```bash
python src/crawler.py
```

O script irá:
1. Conectar à API do GitHub
2. Buscar os 200 repositórios mais populares
3. Filtrar repositórios com pelo menos 100 PRs
4. Coletar PRs que atendem aos critérios
5. Extrair todas as métricas
6. Salvar os dados em arquivos CSV

## Saída

O script gera dois arquivos CSV na pasta `data/`:

### 1. `selected_repositories.csv`
Lista dos repositórios selecionados com informações básicas:
- name
- owner
- full_name
- description
- stars
- forks
- open_issues
- pr_count
- primary_language
- created_at
- updated_at

### 2. `pull_requests_data.csv`
Dados completos de todos os PRs coletados com as métricas:
- repository
- pr_number
- pr_title
- pr_author
- created_at
- closed_at
- merged
- files_changed
- lines_added
- lines_deleted
- total_changes
- analysis_time_hours
- description_chars
- has_description
- participants
- comments_count
- review_comments_count
- total_interactions
- review_count

### Arquivo de Log
- `./data/crawler.log`: Log detalhado da execução

## Estrutura do Projeto

```
lab-codereview-analysis/
├── src/
│   ├── crawler.py              # Script principal de coleta
├── data/                       # Pasta para outputs (gerada automaticamente)
│   ├── selected_repositories.csv
│   ├── pull_requests_data.csv
│   └── crawler.log
├── requirements.txt            # Dependências do projeto
├── .env.example               # Exemplo de configuração
├── .env                       # Configuração (não versionado)
├── .gitignore                # Gitignore
└── README.md                 # Este arquivo
```