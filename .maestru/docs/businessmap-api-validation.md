---
maestru: "0.4"
type: doc
id: businessmap-api-validation
title: Validação da API Businessmap (OpenAPI da instância)
description: Matriz de endpoints/campos da API v2 da instância cttv8, paginação e rate limits, validada contra o OpenAPI público.
tags: [api, businessmap, discovery]
owner: developer
created: 2026-10-21
updated: 2026-10-21
---

# Validação da API Businessmap

<!-- maestru:summary -->
<!-- /maestru:summary -->

Fonte: `https://cttv8.kanbanize.com/openapi` (spec em `/openapi/json`), OpenAPI 3.0.0, "Businessmap API v2", 442 paths.
Base URL: `https://cttv8.kanbanize.com/api/v2`. Validado em 21-10-2026 (work-item A1).

## Matriz de endpoints (só leitura)

| Necessidade | Endpoint | Notas |
|---|---|---|
| Board | `GET /boards`, `GET /boards/{board_id}` | `board_ids=96` já testado com sucesso |
| Estrutura (workflows, lanes, colunas) | `GET /boards/{board_id}/currentStructure` | Base do mapeamento de estados (só leitura) |
| Histórico da estrutura | `GET /boards/{board_id}/structureRevisions[/{revision}]`, `.../currentStructure/revision` | Detetar mudanças de colunas |
| Colunas / lanes / workflows | `GET /boards/{board_id}/columns`, `/lanes`, `/workflows` | |
| Colunas de cycle time | `GET /boards/{board_id}/effectiveCycleTimeColumns`, `/workflows/{workflow_id}/cycleTimeColumns` | Define início/fim de cycle time na instância |
| Cartões (lista) | `GET /cards?board_ids=96` | Filtros, `fields`, `expand` (abaixo) |
| Cartão (detalhe) | `GET /cards/{card_id}` | Preferir `GET /cards?card_ids=` para lotes |
| Histórico do cartão | `GET /cards?...&expand=transitions,lead_time_per_column,block_times` | Schema dos campos expandidos **não documentado** → confirmar com amostras (A2) |
| Revisões do cartão | `GET /cards/{card_id}/revisions` | Alternativa/complemento às transitions |
| Bloqueios | `GET /cards?is_blocked=1`, campos `is_blocked`, `block_reason`, `current_block_time`; `GET /cards/{card_id}/blockReason`; `GET /boards/{board_id}/blockReasons` | |
| Tempo registado | `GET /loggedTime` (paginado) ou `expand=logged_times` | |
| Utilizadores | `GET /users`, `GET /users/{user_id}` | `fields=user_id,username,realname` |
| Tipos de cartão | `GET /boards/{board_id}/cardTypes` | |
| Limites da API | `GET /apiLimits` | Ler limites reais da instância |

**Sprints:** a API não tem conceito de sprint/iteração (0 ocorrências no spec). Confirma a decisão de definir sprints por intervalos de datas (A5).

## `GET /cards` — parâmetros relevantes

- Filtros: `board_ids`, `workflow_ids`, `state` (`active|archived|discarded`), `column_ids`, `lane_ids`, `owner_user_ids`, `type_ids`, `is_blocked`.
- Datas (sync incremental e métricas): `last_modified_from/_to`, `created_from/_to`, `first_start_*`, `first_end_*`, `last_start_*`, `last_end_*`, `archived_from/_to`, `discarded_from/_to`, `in_current_position_since_*` (variantes `*_date`).
- `fields`: `card_id, title, custom_id, owner_user_id, type_id, size, priority, color, deadline, reporter, created_at, revision, last_modified, in_current_position_since, board_id, workflow_id, column_id, lane_id, section, position, last_column_id, last_lane_id, archived_at, discarded_at, is_blocked, block_reason, current_block_time, current_logged_time, current_cycle_time, child_card_stats, first_request_time, first_start_time, first_end_time, last_request_time, last_start_time, last_end_time`, entre outros.
- `expand`: `custom_fields, tag_ids, co_owner_ids, subtasks, linked_cards, transitions, block_times, logged_times, lead_time_per_column, card_outcomes, last_comment`, entre outros.
- Cartões arquivados exigem `state=archived` em pedido separado.

## Paginação

- Sempre paginado: `page` (1 por omissão) e `per_page` (omissão 200, **máximo 1000**).
- Resposta: `data.pagination = { all_pages, current_page, results_per_page }`, `data.data = [...]`.

## Rate limits

- Por omissão: **600 pedidos/hora** e **30 pedidos/minuto** (confirmar valores reais com `GET /apiLimits`).
- Cabeçalhos: `X-RateLimit-PerHour-Limit`, `X-RateLimit-PerHour-Remaining`, `X-RateLimit-PerMinute-Limit`, `X-RateLimit-PerMinute-Remaining`.
- Excesso devolve `429`; não há `Retry-After` documentado → backoff baseado nos cabeçalhos (C1).

## Pendente (A2)

- Amostras reais anonimizadas do Board 96 com `expand=transitions,block_times,lead_time_per_column` para fixar o schema.
- Valores reais de `GET /apiLimits`.
