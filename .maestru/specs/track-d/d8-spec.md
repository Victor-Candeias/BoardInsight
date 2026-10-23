---
maestru: "0.4"
type: work-spec
id: d8-spec
title: "D8 — Página Horas (tempo registado)"
template: implementation-plan-v1
work-item: track-d/D8
owner: developer
created: 2026-10-23
---

# D8 — Página Horas (tempo registado)

## Overview

Até ao D8 só se guardava `current_logged_time` (total acumulado por cartão, sem data nem utilizador), o que não
permite um relatório por período e por pessoa. O Businessmap expõe `GET /loggedTime` (OpenAPI da instância) com uma
linha por registo: `logged_time_id, parent_card_id, card_id, subtask_id, lane_id, column_id, user_id, category_id,
date (YYYY-MM-DD), time (segundos), comment, logged_at`. Filtros: `card_ids`, `user_ids`, `category_ids`,
`from_date/to_date` (pela `date`), `logged_from(_date)/logged_to(_date)` (pela data de registo),
`include_logged_time_for_subtasks`, paginação até 1000. **Não filtra por board.**

## Implementation

### Fase 1 — Recolha no sync

- `BusinessmapClient.iter_logged_times(**filters)` pagina `/loggedTime`; DTO tolerante `BmLoggedTime`.
- `services/logged_times.py` chamado pelo `SyncService._run` depois de ler os cartões e antes de escrever:
  - janela de reconciliação: `from_date = hoje (Europe/Lisbon) − LOGGED_TIME_SYNC_DAYS` (35); na primeira recolha do
    board, `RETENTION_HISTORY_DAYS` (183);
  - segundo pedido `logged_from_date = último sync de horas − 1 dia` para apanhar registos novos com datas antigas
    (só upsert);
  - sempre `include_logged_time_for_subtasks=1` (o filtro de subtarefas é feito na consulta);
  - só ficam entradas do board: `column_id`/`lane_id` da estrutura do board ou `card_id` de um cartão do board;
  - escrita: upsert por `loggedTimeId`; remove as entradas do board na janela que deixaram de vir (editadas/apagadas);
  - falha (403, 429 esgotado, rede) → aviso em `metadataWarnings`, `loggedTimeError` no board, sync continua.
- Collection `logged_times` (`boardId, loggedTimeId, cardId, parentCardId, subtaskId, userId, categoryId, laneId,
  columnId, date (meia-noite UTC do dia), seconds, comment, loggedAt, seenAt`), índices
  `(boardId, loggedTimeId)` único, `(boardId, date)`, `(boardId, userId, date)` e TTL em `date` (retenção do histórico).
- Board: `loggedTimeSyncedAt`, `loggedTimeError`.

### Fase 2 — API

`GET /api/v1/boards/{id}/hours` com `from`, `to`, `granularity` (como as outras páginas), `userId` (vazio = todos) e
`includeSubtasks` (omissão `true`). Resposta: `available`, `warning`, `period`, `buckets`, `users` (pessoas com
registos no board), `totalSeconds`, `entryCount`, `cardCount`, `peopleCount`, `dayCount`, `byUser[]` (com `series`
em segundos por bucket) e `entries[]` (máx. 2000, `truncated`).

### Fase 3 — Página Horas

`/hours` no grupo "Equipa": período e agrupamento, seletor "Utilizador" (Todos | pessoa), caixa "Incluir subtarefas",
KPIs (total, registos, cartões, pessoas/dias), gráfico de barras empilhadas por período, tabela por utilizador
(clicar escolhe a pessoa) e tabela de registos com ligação ao cartão. Horas em `HH:mm` (`formatHours`). PDF.

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `backend/app/integrations/businessmap.py` | Modify | `iter_logged_times` |
| `backend/app/models/businessmap.py` | Modify | DTO `BmLoggedTime` |
| `backend/app/services/logged_times.py` | Create | Recolha/reconciliação e relatório |
| `backend/app/services/sync.py` | Modify | Chamar a recolha no sync |
| `backend/app/core/config.py`, `.env.example`, `deploy/windows/env.windows` | Modify | `LOGGED_TIME_SYNC_DAYS` |
| `backend/app/core/indexes.py` | Modify | Índices de `logged_times` |
| `backend/app/api/v1/delivery.py` | Modify | Endpoint `/hours` |
| `backend/tests/businessmap_fake.py`, `backend/tests/test_hours.py` | Modify/Create | Fake e testes |
| `frontend/src/api/hours.ts` | Create | Tipos e cliente |
| `frontend/src/pages/HoursPage.tsx`, `HoursPage.test.tsx` | Create | Página e testes |
| `frontend/src/charts/HoursChart.tsx` | Create | Gráfico |
| `frontend/src/lib/format.ts`, `components/KpiCard.tsx`, `components/nav.ts`, `App.tsx` | Modify | HH:mm, KPI em texto, menu, rota |
| Versões 0.3.0 (backend, frontend, desktop) | Modify | Novo pacote |
| `.maestru/docs/*.md`, `README.md` | Modify | Documentação |
