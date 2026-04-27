# Sprint 2 - Escopo operacional (200 repositórios + cap de PRs)

## Objetivo

Manter os 200 repositórios da etapa de seleção, mas tornar a coleta de PRs operacionalmente viável para a Sprint 2 limitando o número de PRs elegíveis por repositório.

## Decisão de escopo

- Repositórios: manter 200.
- PRs: limitar em `MAX_ELIGIBLE_PRS_PER_REPO` (padrão 100) por repositório.
- Filtros de elegibilidade do enunciado permanecem inalterados.

## Justificativa

Coleta completa de todos os PRs elegíveis nos 200 repositórios exige volume de requisições incompatível com o prazo e com limites da API. O cap por repositório reduz o custo total e permite entrega de dataset e relatório preliminar na Sprint 2.

## Implicações metodológicas

- O dataset da Sprint 2 não representa censo completo de todos os PRs elegíveis.
- Existe risco de viés de recência ao priorizar PRs mais recentemente atualizados.
- A limitação deve ser explicitada no relatório como ameaça à validade externa.

## Reprodutibilidade

- Configurações relevantes em `.env`:
  - `MAX_ELIGIBLE_PRS_PER_REPO`
  - `MAX_CLOSED_PRS_PAGES`
  - `CHECKPOINT_FILE`
- O progresso é salvo por repositório no checkpoint para retomada sem retrabalho.
