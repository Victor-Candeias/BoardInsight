---
maestru: "0.4"
type: doc
id: readme-analysis-report
title: Relatório de análise do README
description: Análise do README (spec v1.0) com questões em aberto, inconsistências, riscos e work-items propostos.
tags: [report, planning]
owner: developer
created: 2026-10-21
updated: 2026-10-21
---

# Relatório de análise do README

<!-- maestru:summary -->
<!-- /maestru:summary -->

Estado: o repositório tem apenas `README.md` (spec Businessmap Analytics v1.0). Não existem work-items, tracks, specs nem código.

## 0. Decisões tomadas (21-10-2026)

- Utilizador único (tech lead), rede local: **sem autenticação/perfis/users** no MVP; sem questão RGPD.
- Board 96 por omissão; board ativo configurável; colunas podem diferir por board.
- Mapeamento de estados derivado das colunas do board, **só leitura**.
- Board 96 **usa sprints**: secção Scrum entra (depende de identificar a sprint, A5).
- Exportações no MVP: **CSV, JSON e PDF**.
- Python 3.13.5; build do frontend na mesma máquina.
- Teste do `GET /api/v2/boards?board_ids=96` OK; endpoints de cartões/histórico **ainda por validar** (A1/A2).

- Sprints identificadas por **intervalos de datas** (A5 reformulado). Confirmado para o Board 96 (21-10-2026).
- **Sem backups nem restauro**: a app só lê o estado atual (G2 reduzido a hardening do MongoDB; questão 15 fechada). Dados históricos perdidos são recolhidos de novo pela API/snapshots.

- Relatórios agendados **por sprint** (não semanal/mensal) — F4 depende de A5.
- **Sem HTTPS** interno (HTTP na LAN); questão 14 fechada.
- UI em **PT-PT** e timezone **Europe/Lisbon**; questão 17 fechada.
- OpenAPI da instância validado (A1): ver `businessmap-api-validation`. Endpoints e paginação/rate limits documentados (questões 8 e 9); schema dos campos `expand` (transitions, block_times) fica para amostras reais (A2).

- **Retenção** (questão 7 fechada): os gráficos mostram **6 meses** de histórico. `board_snapshots` e `card_events` são guardados 6 meses (~183 dias); `raw` 30 dias; `sync_runs` 90 dias; exports 30 dias (`EXPORT_RETENTION_DAYS`); `cards` mantém sempre o estado atual. A limpeza é automática (TTL index ou job de limpeza).
- **Scheduler** (questão 12 fechada): **timer systemd** (`businessmap-sync.timer`) a correr a sync a cada **30 minutos**, separado do backend (sem APScheduler). A UI tem um **botão de refresh** que pede uma sync manual. Lock por board para evitar syncs ao mesmo tempo.
- **Fila de jobs** (questão 13 fechada): coleção **`jobs` no MongoDB** + serviço systemd **`businessmap-worker`** que executa a sync manual (botão de refresh) e as exportações PDF. Estados: pendente → a correr → concluído/erro. O worker e o timer de 30 min usam o mesmo código de sync e o mesmo lock por board, por isso nunca há duas syncs ao mesmo tempo.
- **Biblioteca UI** (questão 16 fechada): **shadcn/ui** (Tailwind + Radix) + **TanStack Table** para tabelas; gráficos com **Recharts**.

- **Sprints por board** (A5, 21-10-2026): aceitam as duas formas. (a) **Cadência fixa**: data de início + duração (ex.: 14 dias), com sprints geradas automaticamente. (b) **Lista explícita**: cada sprint com nome, início e fim; quando existe, prevalece sobre a cadência. Pressuposto: a resposta "sim" foi lida como "ambas"; confirmar se só uma das formas é precisa.
- **Nome** do repositório e das pastas: **BoardInsight** (substitui `businessmap-analytics/` do README).
- **Configuração**: um ficheiro **`.env`** (substitui `backend.env` em `/etc/...`), com permissões 600.
- **Logs** (recomendação adotada): **journald**. Os serviços systemd escrevem JSON para stdout/stderr e o journald trata da rotação. Limites em `journald.conf`: `SystemMaxUse=200M`, `MaxRetentionSec=30day`. Assim não há rotação de ficheiros para gerir e as escritas no eMMC ficam limitadas. Consulta: `journalctl -u businessmap-*`. Os logs não podem ter a API Key (B5/G4).

- **Hardware** (A4, recolhido a 21-10-2026, host `homework`): Intel Atom x5-Z8350, 4 cores a 1,44–1,92 GHz, **sem AVX** (só SSE4.2); RAM **1,9 GiB** (1,3 GiB já em uso, swap 1,5 GiB com 870 MiB usados); disco eMMC de 28,9 GB; Debian 13 (trixie), kernel 6.12. Consequências:
  - Sem AVX: MongoDB ≥ 5.0 não arranca; **4.4 é a versão máxima** (confirma o README).
  - MongoDB **já instalado e a correr** no servidor (11a fechada): **v4.4.29** (último patch da série 4.4), binários em `/opt/mongodb44/bin/` (tarball `ubuntu2004` x86_64, OpenSSL 1.1.1w, tcmalloc).
  - RAM muito apertada: limitar a cache WiredTiger (ex.: 0,25 GB), 1 worker uvicorn e PDF leve (sem Chromium).
  - Disco (`/dev/mmcblk1p2` em `/`): 26 GB, **11 GB livres** (57% usado). Chega para a app, o MongoDB com 6 meses de histórico e os exports.
  - RAM em uso: a maior parte são **3 sessões do Copilot CLI** (~0,95 GiB RSS; uma delas parada desde as 21:41). Os outros processos são pequenos: `mongod` ~60 MB, `vccteamforge` ~86 MB, outra app Python ~38 MB. Sem as sessões do Copilot, ficam ~1,5 GiB livres para a app.
  - **Build do frontend nesta máquina** (decidido). Vai ser lento; fechar as sessões do Copilot durante o build e, se for preciso, limitar o heap do Node (`NODE_OPTIONS=--max-old-space-size=...`).

Questão 11 fechada (A4 concluído). A3 concluído. Sem questões numeradas em aberto.

Work-items criados no Maestru: 34 (A1–A5, B1–B7, C1–C6, D1–D3, E1–E5, F1–F4, G1–G4) em 7 tracks, com dependências. G1 (autenticação) foi removido; a tabela da secção 4 é a proposta original.

## 1. Questões em aberto

### Negócio / âmbito
1. **Autenticação**: haverá vários utilizadores? Login local, reverse proxy ou sem login (§5.9, §18)? Condiciona `users`, perfis e HTTPS.
2. **Boards**: só o Board 96 ou vários desde o início? Os campos/colunas diferem entre boards?
3. **Definição de "Done"/início**: quais colunas mapeiam `todo`/`inProgress`/`done` no Board 96 (`stateMapping` vazio)?
4. **Sprints**: o Board 96 usa sprints? Se não, §5.7 sai do âmbito.
5. **Relatórios**: formatos obrigatórios no MVP (README exige só CSV+JSON; XLSX/PDF ficam para fase 5)? Relatórios agendados (semanal/mensal) entram quando?
6. **Developers**: política de apresentação por pessoa (RGPD / avaliação individual) — quem pode ver?
7. **Retenção**: prazo para `raw`, snapshots, `sync_runs` e exports (só `EXPORT_RETENTION_DAYS=30` definido).

### Técnicas
8. **Endpoints reais** de cartões, histórico, eventos, bloqueios, utilizadores: desconhecidos até validar o OpenAPI (§7.2).
9. **Rate limits e paginação** da API Businessmap: desconhecidos.
10. **Versão de Python** no Debian e compatibilidade com FastAPI/Pydantic/PyMongo/APScheduler; Node só para build (noutra máquina?).
11. **Hardware**: CPU (AVX), RAM, disco não medidos.
12. **Scheduler**: APScheduler embebido vs serviço/timer systemd? O README lista ambos (§2 vs §13 `businessmap-sync.timer`).
13. **Fila de jobs**: "enfileirar sync/exportação" sem broker — usar coleção Mongo, processo dedicado? Não definido.
14. **HTTPS interno**: certificado próprio/CA interna?
15. **Backups**: destino, frequência, cifragem e responsável pelo restauro.
16. **Biblioteca de componentes** UI não escolhida.
17. **Idioma** da UI (PT-PT?) e timezone de apresentação (Europe/Lisbon?).

## 2. Inconsistências / lacunas no README

- §1 diz "novo projeto independente"; o repositório atual chama-se BoardInsight e §4 usa `businessmap-analytics/` — confirmar nome final do repo/pastas. **Decidido: BoardInsight.**
- `.env.example` (§12) tem `MONGODB_URI=******…` (valor corrompido/mascarado) — corrigir para `mongodb://user:pass@127.0.0.1:27017/...` fictício.
- §13 usa `backend.env` em `/etc/...`; §4/§12 falam de `.env` — padronizar. **Decidido: `.env`.**
- Índice `board_snapshots (boardId, capturedAt)` unique está ok, mas `card_events` sem identificador externo definido.
- `report_exports` guarda metadados mas o ficheiro vive em `EXPORT_DIR`: falta definir limpeza (`expiresAt` sem TTL index explícito).
- Utilizadores (`users`) e autenticação de endpoints não aparecem na tabela REST (§10): faltam `/auth/*` e gestão de utilizadores; faltam endpoints para `stateMapping`, DELETE/PATCH de boards, e leitura de `report_exports`/agendamentos.
- Endpoints de métricas listados: throughput, cycle-time, wip; faltam lead-time, CFD, bloqueios, aging, developers.
- `/health` e `/ready` fora do prefixo `/api/v1` — garantir regra de proxy Nginx.
- Testes: não há estratégia de mock da API Businessmap (fixtures anonimizadas) nem de CI.
- Sem política de logs/rotação concreta (journald vs ficheiro). **Decidido: journald** (ver secção 0).
- Sem plano de migração de índices/esquema Mongo.

## 3. Riscos

| Risco | Impacto | Ação |
|---|---|---|
| MongoDB 4.4 EOL | Segurança | Isolar, auth, backups (WI-ops) |
| Histórico indisponível | Métricas fluxo/CFD | Iniciar snapshots cedo |
| Rate limit desconhecido | Sync falha | Backoff, medir na descoberta |
| API Key | Fuga | Só `.env` 600; teste que logs não a contêm |
| Hardware antigo | Lentidão PDF/agregações | Jobs assíncronos, 1 worker |
| Scheduler duplicado | Syncs concorrentes | Lock por board |

## 4. Work-items propostos (ainda NÃO criados)

Tracks sugeridas: `track-a` Descoberta, `track-b` Fundação, `track-c` Boards e cartões, `track-d` Dashboards, `track-e` Flow/histórico, `track-f` Reports, `track-g` Operação/segurança.

| ID | Track | Título | Prioridade | Depende de |
|---|---|---|---|---|
| A1 | a | Validar OpenAPI da instância e matriz campos/endpoints | critical | — |
| A2 | a | Recolher amostras anonimizadas do Board 96; documentar rate limit/paginação | critical | A1 |
| A3 | a | Decisões pendentes (auth, done-mapping, sprints, retenção) | high | — |
| A4 | a | Medir hardware e versões (Python, Mongo, CPU/AVX) | high | — |
| B1 | b | Scaffolding backend FastAPI + pyproject + lock de versões | high | A4 |
| B2 | b | Scaffolding frontend React/TS/Vite/Tailwind | high | — |
| B3 | b | Settings Pydantic e gestão segura da API Key, `.env.example` corrigido | high | B1 |
| B4 | b | Ligação MongoDB 4.4, repositórios, índices e `/health` `/ready` | high | B1 |
| B5 | b | Logging estruturado sem segredos | medium | B1 |
| C1 | c | `BusinessmapClient` (httpx, retry/backoff, erros normalizados) + teste Board 96 | critical | A1, B3 |
| C2 | c | DTOs de cartões a partir de respostas reais | high | A2 |
| C3 | c | Sync idempotente paginado com lock e `sync_runs` | critical | C1, C2, B4 |
| C4 | c | Scheduler/job de sync e enfileiramento de sync manual | high | C3 |
| C5 | c | API e página Boards (CRUD, test-connection) | high | B4, C1 |
| C6 | c | API e página Cartões (filtros, paginação, detalhe) | high | C3 |
| D1 | d | Dashboard geral (KPIs, distribuições, filtros globais, aviso de dados desatualizados) | high | C6 |
| D2 | d | Throughput e prazos | medium | D1 |
| D3 | d | Página Developers | low | D1 |
| E1 | e | Recolha de eventos e `board_snapshots` | high | C3 |
| E2 | e | WIP, aging, cycle/lead time, percentis | medium | E1 |
| E3 | e | CFD | medium | E1 |
| E4 | e | Bloqueios e qualidade | low | E1 |
| E5 | e | Scrum/sprints (condicional a A3) | low | A3, E1 |
| F1 | f | Exportação CSV/JSON | high | C6 |
| F2 | f | Exportação XLSX e PDF via job | medium | F1 |
| F3 | f | Definições de relatórios guardadas | medium | F1 |
| F4 | f | Relatórios semanal/mensal agendados | low | F2, C4 |
| G1 | g | Autenticação/perfis (conforme A3) | high | A3, B4 |
| G2 | g | Deploy Debian: systemd, Nginx, utilizador dedicado, docs/deployment-debian.md | high | B1, B2 |
| G3 | g | Hardening MongoDB (auth, bind, firewall) e backups com restauro testado | high | G2 |
| G4 | g | Rate limit em sync/export e CORS restrito | medium | C4, F1 |
| G5 | g | Testes de aceitação operacionais (reboot, logs sem credenciais) | medium | G2 |
| X1 | b | Pipeline de testes (pytest, Vitest) e fixtures Businessmap mock | medium | B1, B2 |
| X2 | b | Docs: architecture, businessmap-api-validation, metrics-definitions | medium | A1 |

## 5. Caminho crítico do MVP

A1 → A2 → C1 → C2 → C3 → C6 → D1 → F1 (+ G2/G3 para operação).

## 6. Próximos passos sugeridos

1. Responder às questões 1–4 e 8–12.
2. Criar as tracks e os work-items A1–A4 (via `maestru sql INSERT`).
3. Corrigir as inconsistências da secção 2 no README.
