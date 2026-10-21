---
maestru: "0.4"
type: work-track
id: track-c
title: Boards e cartões
created: 2026-10-21
description: Boards e cartões
owner: developer
status: active
---

# track-c: Boards e cartões

## Summary

<!-- maestru:summary -->
| ID | Title | Status | Created | Owner | Priority | Completed | Template | Blocked By | Spec |
|---|---|---|---|---|---|---|---|---|---|
| C1 | BusinessmapClient (httpx, retry/backoff, erros normalizados) e teste Board 96 | backlog | 2026-10-21 | developer | critical |  |  | A1, B3 |  |
| C2 | DTOs de cartões a partir de respostas reais | backlog | 2026-10-21 | developer | high |  |  | A2 |  |
| C3 | Sync idempotente paginado com lock e sync_runs | backlog | 2026-10-21 | developer | critical |  |  | C1, C2, B4 |  |
| C4 | Scheduler de sync e enfileiramento de sync manual | backlog | 2026-10-21 | developer | high |  |  | C3 |  |
| C5 | API e página Boards (trocar board ativo, test-connection, mapeamento de colunas só leitura) | backlog | 2026-10-21 | developer | high |  |  | B4, C1 |  |
| C6 | API e página Cartões (filtros, paginação, detalhe) | backlog | 2026-10-21 | developer | high |  |  | C3 |  |
<!-- /maestru:summary -->

<!-- maestru:work-items-list -->
| ID | Title | Status | Created | Owner | Priority | Completed | Template | Blocked By | Spec |
|---|---|---|---|---|---|---|---|---|---|
| C1 | BusinessmapClient (httpx, retry/backoff, erros normalizados) e teste Board 96 | done | 2026-10-21 | developer | critical | 2026-10-21 |  | track-a/A1, track-b/B3 |  |
| C2 | DTOs de cartões a partir de respostas reais | done | 2026-10-21 | developer | high | 2026-10-21 |  | track-a/A2 |  |
| C3 | Sync idempotente paginado com lock e sync_runs | done | 2026-10-21 | developer | critical | 2026-10-21 |  | C1, C2, track-b/B4 |  |
| C4 | Timer systemd de sync (30 min), worker de jobs (MongoDB) e botão de refresh na UI | done | 2026-10-21 | developer | high | 2026-10-21 |  | C3 |  |
| C5 | API e página Boards (trocar board ativo, test-connection, mapeamento de colunas só leitura) | done | 2026-10-21 | developer | high | 2026-10-21 |  | track-b/B4, C1 |  |
| C6 | API e página Cartões (filtros, paginação, detalhe) | done | 2026-10-21 | developer | high | 2026-10-21 |  | C3 |  |
<!-- /maestru:work-items-list -->
