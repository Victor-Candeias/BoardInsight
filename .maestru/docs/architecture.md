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
| `report_definitions` | Definições de relatórios guardadas | permanente |
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

## Jobs e worker

- `POST /api/v1/boards/{id}/sync` cria um job `sync_board` (devolve o job ativo existente se já houver um, HTTP 200).
- `GET /api/v1/jobs/{id}` e `GET /api/v1/boards/{id}/sync-status` permitem à UI acompanhar (botão **Atualizar** no cabeçalho, polling de 2 s).
- O worker (`app.jobs.worker`) faz polling a cada `WORKER_POLL_SECONDS`; jobs `running` há mais de `JOB_TIMEOUT_MINUTES` passam a `error` (`timeout`).
- `app.jobs.sync` (timer) sai com código 1 se algum board falhar e 2 se faltar a API key.
- Unidades systemd em `deploy/systemd/`.

## Erros da API

Todas as respostas de erro usam `{"error": {"code", "message", "details"?}}` (`api/errors.py`). Erros do Businessmap são mapeados para `businessmap_*` (502/503/404); configuração em falta → 503 `configuration_error`.
