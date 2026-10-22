---
maestru: "0.4"
type: doc
id: architecture
title: Arquitetura do BoardInsight
created: 2026-10-21
description: "Componentes, processos, collections MongoDB e fluxo de dados do BoardInsight."
owner: developer
tags: [architecture, backend, frontend]
updated: 2026-10-21
---

# architecture: Arquitetura do BoardInsight

<!-- maestru:summary -->
<!-- /maestru:summary -->

## Visão geral

```text
Browser (LAN, HTTP)
    |
    v
Nginx :80 ── /            -> frontend/dist (SPA React, PT-PT)
          ── /api/, /health, /ready -> FastAPI (uvicorn, 1 worker) em 127.0.0.1:8000
                                          |
             businessmap-sync.timer (30 min) ──> python -m app.jobs.sync   ─┐
             businessmap-worker (sempre ativo) ─> python -m app.jobs.worker ─┤
                                                                            v
                                     BusinessmapClient (httpx, apikey) ── https://cttv8.kanbanize.com/api/v2
                                                                            |
                                                         MongoDB 4.4 em 127.0.0.1:27017 (base BoardInsight)
```

- O browser nunca fala com o Businessmap nem recebe a API Key; só o backend a lê do `.env` (600).
- A API web **não** executa syncs nem PDFs no pedido HTTP: enfileira um documento em `jobs` e devolve o id.
- O timer de 30 min e o worker usam o mesmo `SyncService` e o mesmo **lock por board** (collection `locks`, com TTL), por isso nunca há duas syncs do mesmo board em simultâneo.
- Logs JSON para stdout → journald (`journalctl -u businessmap-*`), com redação de segredos.

## Processos (systemd)

| Unidade | Comando | Função |
|---|---|---|
| `businessmap-api.service` | `uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1` | API REST `/api/v1`, `/health`, `/ready` |
| `businessmap-sync.timer` → `businessmap-sync.service` | `python -m app.jobs.sync` | Sync de todos os boards ativos + limpeza de retenção + relatórios agendados |
| `businessmap-worker.service` | `python -m app.jobs.worker` | Executa jobs: sync manual (botão refresh), exportações PDF/XLSX |

## Backend (`backend/app`)

| Pasta | Conteúdo |
|---|---|
| `core/` | `config` (Settings/SecretStr), `database` (PyMongo tz-aware), `indexes` (índices e TTL), `logging` (JSON + redação), `errors`, `middleware`, `ratelimit` |
| `integrations/` | `BusinessmapClient` (httpx, retry/backoff, erros normalizados) |
| `models/` | DTOs Pydantic das respostas Businessmap e modelos da API interna |
| `repositories/` | Acesso às collections (boards, cards, card_events, board_snapshots, sync_runs, jobs, locks, report_*) |
| `services/` | boards, sync, cards, dashboard, métricas de fluxo, sprints, exportações, relatórios |
| `jobs/` | Entradas CLI: `sync` (timer + retenção), `worker` (fila `jobs`), `handlers` |
| `api/v1/` | Routers FastAPI |

## Frontend (`frontend/src`)

React + TypeScript + Vite, Tailwind + componentes estilo shadcn/ui, TanStack Query/Table, Recharts.
Páginas: Dashboard, Boards, Cartões, Developers, Fluxo, Bloqueios, Sprints, Relatórios.
O board ativo é escolhido no cabeçalho (guardado no `localStorage`).

## Collections MongoDB

| Collection | Conteúdo | Retenção |
|---|---|---|
| `boards` | Config local + metadados + estrutura (colunas/lanes/secções) + sprints | permanente |
| `cards` | Estado atual normalizado (+ `raw`) | permanente; `raw` 30 dias |
| `card_events` | Transições observadas entre syncs e da API (`transitions`) | 183 dias (TTL) |
| `board_snapshots` | Contagens por coluna/secção em cada sync | 183 dias (TTL) |
| `sync_runs` | Auditoria das syncs (contagens, duração, erros) | 90 dias (TTL) |
| `locks` | Lock por board (`expiresAt`) | TTL |
| `jobs` | Fila de jobs (pendente → a correr → concluído/erro) | `JOB_RETENTION_DAYS` (7) após terminar (TTL) |
| `report_definitions` | Definições de relatórios guardadas (índice único `boardId`+`name`) | permanente |
| `report_exports` | Metadados de ficheiros exportados | 30 dias (TTL + limpeza de ficheiros) |
| `users_cache` | Nomes dos utilizadores Businessmap por board | atualizado em cada sync |

## Fluxo de sincronização

1. Adquirir lock `sync:<boardId>`; criar `sync_run` em execução.
2. Ler estrutura do board (`currentStructure`), tipos e utilizadores.
3. Ler todas as páginas de `GET /cards` (ativos) e arquivados recentes (`state=archived`, 183 dias).
4. Só se **todas** as páginas forem lidas: upserts idempotentes em `cards`, eventos de transição, snapshot, `lastSuccessfulSyncAt`.
5. Em falha parcial: nada é marcado como removido/concluído; `sync_run` fica com erro.
6. Libertar lock.

Cartões ativos que deixam de aparecer recebem `missingSince` (nunca são apagados). Ver `services/sync.py`.

### Histórico (hooks da sync, `services/history.py`)

- `card_events` com `eventKey` único (reprocessar não duplica):
  - `source="sync"`, `type="field_change"`: diferenças nos `TRACKED_FIELDS` (coluna, lane, secção, estado, bloqueio, responsável, estado do cartão) entre a sync anterior e a atual; `occurredAt` = hora da sync que observou, `previousObservedAt` = sync anterior.
  - `source="sync"`, `type="created"`: cartão novo visto depois da primeira sync (na primeira sync não se geram eventos).
  - `source="api"`, `type="transition"`: cada permanência em `transitions` da API → evento com coluna/lane/estado de origem e destino, `occurredAt` = início. Só reprocessado quando a lista do cartão muda.
- `board_snapshots` (uma por sync com sucesso): `total`, `blocked`, `byStatus`, `byColumn` (com `cardIds` por coluna), `byLane` e `cardIds` por estado (backlog/todo/in_progress/done) dos cartões ativos não em falta.
- Syncs com erro não escrevem histórico. O detalhe do cartão mostra só eventos `sync` (as transições da API já aparecem no percurso) e `eventsSince`/`snapshotsSince`.

## Jobs e worker

- `POST /api/v1/boards/{id}/sync` cria um job `sync_board` (devolve o job ativo existente se já houver um, HTTP 200).
- `GET /api/v1/jobs/{id}` e `GET /api/v1/boards/{id}/sync-status` permitem à UI acompanhar (botão **Atualizar** no cabeçalho, polling de 2 s).
- O worker (`app.jobs.worker`) faz polling a cada `WORKER_POLL_SECONDS`; jobs `running` há mais de `JOB_TIMEOUT_MINUTES` passam a `error` (`timeout`).
- `app.jobs.sync` (timer) sai com código 1 se algum board falhar e 2 se faltar a API key.
- `POST /api/v1/reports/export` (`{boardId, format: pdf|xlsx, title?, filters, from?, to?, sort?, columns?}`) valida os filtros (mesmos nomes de `/cards`), verifica o limite (`EXPORT_MAX_ROWS`; PDF `EXPORT_PDF_MAX_ROWS`) e cria um `report_exports` + job `report_export` (HTTP 202). O worker (`services/reports.py`) escreve `EXPORT_DIR/<exportId>.<formato>`: XLSX (folhas Resumo e Cartões, datas locais, texto nunca interpretado como fórmula) ou PDF A4 paisagem (resumo, indicadores, tabela de cartões; fonte DejaVu se existir).
- `GET /api/v1/reports/exports?boardId=` (recentes), `GET /api/v1/reports/exports/{id}` (estado; passa a `error` se o job falhou) e `GET /api/v1/reports/exports/{id}/download` (409 `export_not_ready`/`export_failed`, 410 `export_expired`). Metadados expiram por TTL e ficheiros pela retenção (`EXPORT_RETENTION_DAYS`).
- Definições guardadas (`report_definitions`, nome único por board, sem dono: utilizador único): `GET /api/v1/reports?boardId=` (com `filtersLabel` legível), `POST /api/v1/reports` (`{boardId, name, params}`; 409 `report_name_taken`), `GET|PUT|DELETE /api/v1/reports/{id}`, `POST /api/v1/reports/{id}/export` (`{format}`; sem datas fixas usa o último mês). `params` = mesmo formato de `POST /reports/export` (título, filtros, período, ordenação, colunas).
- Agendamento por sprint: `schedule {enabled, trigger: "sprint_end", formats, since, lastSprintId, lastRunAt, lastExportIds, lastError}` na definição (POST/PUT `/reports`). O timer de sincronização chama `run_scheduled_reports` após a retenção: para cada definição ativa gera uma exportação por formato da última sprint terminada depois de `since` (período = datas da sprint, `trigger: "schedule"`), uma única vez por sprint; erros ficam em `lastError`.
- Proteções da API (sem autenticação, LAN): rate limit em memória por IP (janela de 60 s; a API tem um só worker) em `POST /boards/{id}/sync` (`RATE_LIMIT_SYNC_PER_MINUTE`) e nas exportações `GET /boards/{id}/cards/export`, `POST /reports/export` e `POST /reports/{id}/export` (`RATE_LIMIT_EXPORT_PER_MINUTE`) → 429 `rate_limited` com `Retry-After`. CORS só para as origens explícitas de `CORS_ORIGINS` (sem `*`); escritas com `Origin` diferente do `Host` e fora dessa lista → 403 `origin_not_allowed`.
- Unidades systemd em `deploy/systemd/` (`businessmap-api`, `businessmap-worker`, `businessmap-sync` + timer), site Nginx em `deploy/nginx.conf`, limites journald em `deploy/journald/` e instalação com `deploy/install.sh` — ver `deployment-debian`.

## Erros da API

Todas as respostas de erro usam `{"error": {"code", "message", "details"?}}` (`api/errors.py`). Erros do Businessmap são mapeados para `businessmap_*` (502/503/404); configuração em falta → 503 `configuration_error`.

## Filtros e períodos analíticos

- Os filtros de cartões (`api/v1/filters.py`, `services/card_query.py`) são partilhados pela lista de cartões, dashboard e exportações; na UI vivem nos parâmetros do URL (`useCardFilters`).
- Períodos (`services/periods.py`): `from`/`to` (datas locais `Europe/Lisbon`, inclusivas), `granularity` = `day|week|month` (semanas ISO, segunda-feira). Por omissão: último mês (do mesmo dia do mês anterior até hoje; limitado ao fim do mês, ex. 31/03 → 28/02). Máximo de 400 intervalos (422 acima disso).
- `GET /api/v1/boards/{id}/dashboard`: KPIs do estado atual (com filtros), distribuições (estado, coluna, lane, tipo, prioridade, responsável) e evolução criados vs. concluídos por intervalo. A evolução inclui arquivados e ignora os filtros de estado/datas; devolve `dataAsOf` e `stale`.
- `GET /api/v1/boards/{id}/throughput` (filtros + período): cartões com `endTime` no período por intervalo (inclui arquivados, exclui descartados), tamanho somado, média por intervalo (exclui intervalos `partial` cortados pelo período) e totais por tipo. O mesmo critério de conclusão (`services/delivery.completed_query`) é usado no dashboard.
- `GET /api/v1/boards/{id}/deadlines` (filtros): listas de cartões abertos em atraso e a vencer em 7 dias (ordenadas por prazo, máx. 500 com `truncated`, `daysToDeadline`), abertos sem prazo e atrasos por responsável.
- `GET /api/v1/boards/{id}/developers` (filtros exceto responsável/estado/prazos + período): por responsável (inclui "Sem responsável") backlog, a fazer, WIP, bloqueados, em atraso, cartões abertos como co-responsável, idade média/máx. do WIP (`aging_days`; estimada sem data de início), concluídos e série por intervalo. Inclui `disclaimer`: uso pessoal do tech lead, não é avaliação de desempenho.
- `GET /api/v1/boards/{id}/flow` (filtros exceto estado/prazos + período): `leadTime` e `cycleTime` (P50/P85/P95, média, mín./máx.; `smallSample` < 5; `available=false` + `reason` sem dados) dos concluídos no período, `trend` por intervalo, `points` para dispersão, `wip` atual (total, bloqueados, por coluna/lane/responsável) e `aging` do WIP com limiar = cycle time P85 (`aboveP85`).
- `GET /api/v1/boards/{id}/cfd?group=status|column` (período em dias; filtros de texto/responsável/tipo/prioridade aplicados aos `cardIds` dos snapshots com os atributos atuais): `series` e `days` com o último snapshot de cada dia local; `snapshotsSince`; `available=false` + `reason` sem histórico.
- `GET /api/v1/boards/{id}/blockers` (filtros exceto estado/bloqueio/prazos + período): `current` (cartões ativos em aberto bloqueados com motivo, comentário e `currentBlockTimeSeconds`; percentagem do trabalho em aberto; distribuições por motivo/responsável/coluna com dias acumulados) e `history` (bloqueios/desbloqueios observados nas syncs por intervalo e duração dos desbloqueados, `historySince`).
- `GET /api/v1/boards/{id}/quality` (mesmos filtros + período): reaberturas `done` → backlog/todo/in_progress observadas na sync ou nas transições da API (por cartão conta a fonte com mais ocorrências), cartões reabertos, taxa = cartões reabertos ÷ concluídos no período, série por intervalo.
- Sprints (`boards.sprints = {cadence: {start, lengthDays, namePrefix} | null, explicit: [{name, start, end}]}`; a lista explícita prevalece; sem sobreposições): `PUT /api/v1/boards/{id}/sprints/config`; `GET /api/v1/boards/{id}/sprints` (sprints até hoje, máx. 26 na cadência, com velocity, compromisso e cumprimento; `averageVelocity` das últimas 3 terminadas; `upcoming`); `GET /api/v1/boards/{id}/sprints/{sprintId}` (id = data de início; burndown diário, compromisso, adicionados depois). Filtros de texto/responsável/tipo/prioridade.
- Exportação: `GET /api/v1/boards/{id}/cards/export?format=csv|json` com os mesmos filtros e `sort` de `/cards`, sem paginação; resposta em streaming com `Content-Disposition` e `X-Total-Count`; acima de `EXPORT_MAX_ROWS` devolve 422 `export_too_large`. CSV para Excel PT: separador `;`, vírgula decimal, BOM UTF-8, datas locais `AAAA-MM-DD HH:MM`, prefixo `'` contra injeção de fórmulas. JSON: `{meta, items}`.
