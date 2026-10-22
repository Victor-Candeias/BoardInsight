---
maestru: "0.4"
type: work-spec
id: g7-spec
title: "G7 — Instalador Windows (.exe) gerado em Linux"
template: implementation-plan-v1
work-item: track-g/G7
owner: developer
created: 2026-10-22
---

# G7 — Instalador Windows (.exe) gerado em Linux

## Overview

Instalador Windows autónomo (`BoardInsight-Setup-<versão>.exe`) gerado em Linux, que instala Python embutido, backend, frontend compilado, MongoDB e serviços Windows, sem pré-requisitos na máquina destino. Durante a instalação pede o URL da instância Businessmap, a API key (mascarada) e o board inicial. Motivação: work-item G7.

## Decisões

| Tema | Decisão |
|------|---------|
| Servidor web | A própria API (Uvicorn/FastAPI) serve o `frontend/dist` quando `FRONTEND_DIST` está definido — sem Node, Nginx nem Caddy no Windows. Linux inalterado (variável vazia). |
| Serviços | WinSW 2.12 (x64, self-contained): `boardinsight-mongodb`, `boardinsight-api`, `boardinsight-worker`, conta LocalSystem, arranque automático, restart em falha, logs com rotação por tamanho. |
| Sync | Tarefa agendada `BoardInsight\Sync` (30 min, SYSTEM) que corre `sync.cmd`. |
| MongoDB | Community 8.0.x (só `mongod.exe`), `127.0.0.1:27018` (porta dedicada para não colidir com outro MongoDB), `--auth`, cache WiredTiger 1 GB; VC++ Redistributable instalado só se faltar. |
| Utilizadores Mongo | `app.ops.windows_setup` usa a localhost exception para criar `admin` (root, password em `mongodb-admin.secret`) e `boardinsight` (readWrite); passwords geradas com `secrets`. Idempotente. |
| Pastas | Programa em `{autopf}\BoardInsight` (Program Files de 64 bits); dados em `%ProgramData%\BoardInsight` (`.env`, `mongodb\`, `exports\`, `logs\`) com ACL só SYSTEM + Administradores; preservados na desinstalação/atualização (a desinstalação pergunta se apaga os dados). |
| Configuração | Página do instalador: URL (pré-preenchido `https://cttv8.kanbanize.com`), API key mascarada, board (96), porta do site (8080). Validação opcional com `GET /api/v2/boards?board_ids=<id>` (WinHTTP). Instalação silenciosa: `/URL= /BOARD= /PORT=`; a API key vem só da variável de ambiente `BOARDINSIGHT_SETUP_API_KEY` (o Inno grava a linha de comandos no log, por isso nada de `/APIKEY=`). Em atualização, API key vazia mantém a atual. |
| Board inicial | Registado por `windows_setup` (metadados + job `sync_board`) se ainda não existir. |
| Build | `deploy/windows/build-installer.sh` em Linux: `npm run build`, Python embeddable + `pip --platform win_amd64`, ZIP MongoDB, WinSW, Inno Setup 6.7 via Wine 11.0 portátil (driver gráfico `null`, sem root). Downloads com SHA256 fixado em `versions.env`. |
| Python no Windows | `tzdata` adicional (o Windows não tem base IANA para `zoneinfo`). `worker.py` cai para `signal.signal` quando `add_signal_handler` não existe (Windows). Serviços e `sync.cmd` com `PYTHONUTF8=1` (logs em UTF-8). |
| CPU | MongoDB 5+ exige AVX (sem AVX: `0xC000001D`); requisito documentado do PC Windows. |

## Implementation

### Phase 1: Backend compatível com Windows

| Action | File | Details |
|--------|------|---------|
| Modify | `backend/app/core/config.py` | `frontend_dist: Path \| None` (`FRONTEND_DIST`, vazio = desligado) |
| Create | `backend/app/core/frontend.py` | Serve `index.html`, `assets/` (cache imutável) e fallback SPA; nunca para `api/`; bloqueia path traversal |
| Modify | `backend/app/main.py` | Monta o frontend se `FRONTEND_DIST` definido |
| Modify | `backend/app/jobs/worker.py` | `install_stop_handlers` com fallback Windows |
| Create | `backend/app/serve.py` | Arranque Uvicorn com host/porta do `.env` |
| Create | `backend/app/ops/windows_setup.py` | `.env` (password Mongo), utilizadores Mongo, índices, board inicial |

- [x] Testes pytest para frontend, worker e windows_setup

### Phase 2: Pacote e instalador

| Action | File | Details |
|--------|------|---------|
| Create | `deploy/windows/versions.env` | Versões, URLs e SHA256 |
| Create | `deploy/windows/requirements-windows.txt` | `tzdata` |
| Create | `deploy/windows/env.windows` | Modelo do `.env` Windows |
| Create | `deploy/windows/services/*.xml` | WinSW (mongodb, api, worker) |
| Create | `deploy/windows/sync.cmd` | Sync agendada com log rodado |
| Create | `deploy/windows/boardinsight.iss` | Script Inno Setup (página de configuração, serviços, tarefa, firewall, desinstalação) |
| Create | `deploy/windows/build-installer.sh` | Build completo em Linux |

- [x] `.exe` gerado em Linux
- [x] Python embutido arranca sob Wine e importa `app.main` com `tzdata`
- [x] Sob Wine: `windows_setup` contra MongoDB `--auth` (utilizadores, idempotência, código 2 com key inválida); API serve SPA/assets/404 `/api`; worker arranca
- [x] Sob Wine: instalação silenciosa (serviços WinSW com `%BASE%`/`%ProgramData%`, ICACLS, vc_redist, firewall) e desinstalação (dados preservados)
- [ ] Teste de instalação/atualização/desinstalação num Windows real

### Phase 3: Documentação

| Action | File | Details |
|--------|------|---------|
| Create | `.maestru/docs/deployment-windows.md` | Build, instalação, operação |
| Modify | `README.md` | Secção 21 |
| Modify | `.maestru/docs/architecture.md`, `.env.example` | `FRONTEND_DIST` e referência ao Windows |

- [x] Documentação escrita

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `backend/app/core/config.py` | Modify | `FRONTEND_DIST` |
| `backend/app/core/frontend.py` | Create | Servir SPA pela API |
| `backend/app/main.py` | Modify | Montar frontend |
| `backend/app/jobs/worker.py` | Modify | Sinais em Windows |
| `backend/app/serve.py` | Create | Launcher Uvicorn |
| `backend/app/ops/windows_setup.py` | Create | Configuração pós-instalação |
| `backend/tests/test_frontend.py` | Create | Testes do frontend servido pela API |
| `backend/tests/test_windows_setup.py` | Create | Testes do setup Windows |
| `backend/tests/test_jobs.py` | Modify | Teste do fallback de sinais |
| `deploy/windows/*` | Create | Build e instalador |
| `.maestru/docs/deployment-windows.md` | Create | Documentação |
| `README.md` | Modify | Secção Windows |
| `.env.example`, `.maestru/docs/architecture.md` | Modify | `FRONTEND_DIST`, referência ao Windows |
