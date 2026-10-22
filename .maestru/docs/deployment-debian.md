---
maestru: "0.4"
type: doc
id: deployment-debian
title: Deploy no Debian
created: 2026-10-21
description: "Instalação e atualização do BoardInsight no servidor Debian: utilizador dedicado, systemd, Nginx, journald e verificação."
owner: developer
tags: [deployment, operations, debian]
updated: 2026-10-21
---

# Deploy no Debian

<!-- maestru:summary -->
<!-- /maestru:summary -->

Servidor alvo: Debian 13 (trixie), Intel Atom x5-Z8350 sem AVX, 1,9 GiB RAM, eMMC (ver `readme-analysis-report` §0).
HTTP na LAN, sem HTTPS nem autenticação (decisão). MongoDB 4.4.29 já instalado em `/opt/mongodb44/`.

## Estrutura

| Caminho | Dono / modo | Conteúdo |
|---|---|---|
| `/opt/boardinsight/backend/` | root, 755 | Código Python + `.venv` (dependências de `requirements.lock`) |
| `/opt/boardinsight/frontend/dist/` | root, 755 | Build React servido pelo Nginx |
| `/opt/boardinsight/deploy/` | root, 755 | Units, Nginx, journald, `install.sh` |
| `/opt/boardinsight/.env` | boardinsight, **600** | Configuração e segredos (nunca no Git) |
| `/var/lib/boardinsight/exports/` | boardinsight, 750 | Ficheiros de exportação (retenção 30 dias) |

Logs: **journald** (sem ficheiros próprios). Limites em `/etc/systemd/journald.conf.d/boardinsight.conf`
(`SystemMaxUse=200M`, `MaxRetentionSec=30day`). O Nginx escreve em `/var/log/nginx/boardinsight.*.log` (logrotate do Debian).

## Serviços

| Unit | Tipo | Função |
|---|---|---|
| `businessmap-api.service` | simple | Uvicorn com 1 worker em `127.0.0.1:8000` (`MemoryMax=300M`) |
| `businessmap-worker.service` | simple | Fila `jobs`: sync manual e exportações PDF/XLSX (`MemoryMax=400M`) |
| `businessmap-sync.service` + `.timer` | oneshot, 30 min | Sync de todos os boards ativos, retenção e relatórios agendados |

Todas correm como `boardinsight` com `ProtectSystem=strict`, `ProtectHome`, `PrivateTmp`, `NoNewPrivileges` e
escrita apenas em `/var/lib/boardinsight`. Lêem a configuração de `BOARDINSIGHT_ENV_FILE=/opt/boardinsight/.env`.
Se a unit do MongoDB não se chamar `mongod.service`, ajustar `After=` nas três units de serviço.

Nginx (`deploy/nginx.conf` → `/etc/nginx/sites-available/boardinsight`): serve `frontend/dist` com fallback SPA para
`index.html`, cache longa em `/assets/`, e encaminha `/api/`, `/health` e `/ready` para `127.0.0.1:8000`.

## Pré-requisitos

```bash
sudo apt install python3 python3-venv rsync nginx curl nodejs npm
python3 --version        # 3.13.x
node --version           # ≥ 20.19 (Vite 8); o nodejs do Debian 13 serve
/opt/mongodb44/bin/mongod --version
```

Base de dados e utilizador MongoDB com `readWrite` só na base `BoardInsight` (hardening em G2).

## Instalação e atualização

A partir de um checkout do repositório no servidor:

```bash
sudo deploy/install.sh                      # instala/atualiza e arranca os serviços
sudo deploy/install.sh --skip-frontend-build  # reutiliza frontend/dist do checkout
sudo deploy/install.sh --no-start           # só copia e configura
```

O script é idempotente: cria o utilizador de sistema `boardinsight` (`nologin`), as pastas, copia o código com `rsync`
(sem `.git`, `.env`, `.venv`, `node_modules`), instala as dependências fixadas, faz o build do frontend
(`NODE_HEAP_MB`, por omissão 768), instala units/Nginx/journald, valida `nginx -t`, ativa
`businessmap-api`, `businessmap-worker` e `businessmap-sync.timer` e testa `/health` e `/ready`.

Na primeira instalação cria `/opt/boardinsight/.env` a partir do `.env.example` (600). Preencher com
`sudoedit /opt/boardinsight/.env` (`MONGODB_PASSWORD`, `BUSINESSMAP_API_KEY`) e reiniciar:

```bash
sudo systemctl restart businessmap-api businessmap-worker
```

O build do frontend no Atom é lento: fechar outros processos pesados durante o build. Se o site `default` do Nginx
estiver ativo, removê-lo (`sudo rm /etc/nginx/sites-enabled/default && sudo systemctl reload nginx`).

## Verificação

```bash
systemctl status businessmap-api businessmap-worker businessmap-sync.timer
systemctl list-timers businessmap-sync.timer
curl -s http://127.0.0.1/health            # {"status":"ok"}
curl -s http://127.0.0.1/ready             # 200 com mongodb e businessmap_api_key ok
journalctl -u 'businessmap-*' -n 50 -o cat # logs JSON, sem segredos
```

Depois de um reboot os serviços e o timer arrancam sozinhos (testes de aceitação em G4).
