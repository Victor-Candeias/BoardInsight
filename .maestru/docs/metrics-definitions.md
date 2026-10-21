---
maestru: "0.4"
type: doc
id: metrics-definitions
title: Definições das métricas
created: 2026-10-21
description: "Definição exata de cada métrica (estados, throughput, lead/cycle time, WIP, aging, CFD, bloqueios, sprints) e dados necessários."
owner: developer
tags: [metrics, flow]
updated: 2026-10-21
---

# metrics-definitions: Definições das métricas

<!-- maestru:summary -->
<!-- /maestru:summary -->

Todas as datas são guardadas em UTC e apresentadas em **Europe/Lisbon**. Os buckets de dia/semana/mês
são calculados na timezone de apresentação. Uma métrica sem dados suficientes devolve `available=false`
com o motivo — nunca um zero fictício.

## Estados

O estado interno deriva da **secção** Businessmap da coluna atual (só leitura, sem mapeamento manual):

| Secção | Nome Businessmap | Estado interno |
|---|---|---|
| 1 | Backlog | `backlog` |
| 2 | Requested | `todo` |
| 3 | Progress | `in_progress` |
| 4 | Done | `done` |
| 5 | Archive (Ready to archive) | `done` |
| — | cartão `archived` com data de fim | `done` |
| — | cartão `discarded` | `discarded` |

"Ativo" = `todo` + `in_progress`. As colunas de cycle time da instância (`effectiveCycleTimeColumns`) são guardadas e mostradas na página Boards.

## Datas de referência (campos da API)

- **Criação**: `created_at`.
- **Início**: `first_start_time` (primeira entrada em Progress).
- **Fim**: `last_end_time` (última entrada em Done); se nulo, `first_end_time`.

## Indicadores

| Métrica | Definição | Dados |
|---|---|---|
| Throughput | N.º de cartões com data de fim no bucket (dia/semana ISO/mês) | Data de fim; inclui arquivados até 183 dias |
| Lead time | Fim − criação, em dias | Cartões concluídos no período |
| Cycle time | Fim − início, em dias | Cartões concluídos com início conhecido |
| Percentis | P50/P85/P95 por interpolação linear (método do NumPy por omissão) | ≥ 1 valor; com < 5 valores é marcado como amostra pequena |
| WIP | Cartões ativos em `in_progress`, por coluna, lane e responsável | Estado atual |
| Aging WIP | Agora − início (`first_start_time`) dos cartões `in_progress`; sem início usa `in_current_position_since` (marcado como estimado) | Estado atual |
| Vencidos | `deadline` < agora e estado ≠ `done`/`discarded` | Deadline |
| A vencer | `deadline` nos próximos 7 dias e não concluído | Deadline |
| Bloqueados | `is_blocked=1`; duração = `current_block_time` (segundos da API) | Estado atual |
| CFD | Por dia, último snapshot desse dia: n.º de cartões por coluna/estado | `board_snapshots` (desde o início da recolha) |
| Reaberturas | Transições observadas de `done` para outro estado | `card_events` (desde o início da recolha) |
| Dados desatualizados | `lastSuccessfulSyncAt` há mais de `STALE_AFTER_MINUTES` (90) | `boards` |

## Sprints (por board, intervalos de datas)

- **Cadência fixa**: início + duração em dias → sprints geradas automaticamente.
- **Lista explícita**: nome, início, fim; prevalece sobre a cadência quando existe.
- **Concluído na sprint (velocity)**: cartões com data de fim dentro da sprint (contagem e soma de `size`).
- **Compromisso**: cartões ativos (`todo`/`in_progress`) no primeiro snapshot da sprint (ids guardados no snapshot).
- **Burndown**: por dia, cartões do compromisso ainda não concluídos (último snapshot do dia).
- Sem snapshot no início da sprint → compromisso/burndown indisponíveis (velocity continua disponível).

## Integridade

- Não se calculam durações históricas a partir apenas da coluna atual.
- Snapshots e eventos só existem desde o início da recolha; a UI mostra essa data.
- Contagens por pessoa (Developers) são de uso pessoal do tech lead e não são uma avaliação de desempenho.
