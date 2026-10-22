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
Arrancam depois de `mongodb44.service` (unit existente do MongoDB 4.4 em `/opt/mongodb44/`, config `/etc/mongodb44.conf`).

Nginx (`deploy/nginx.conf` → `/etc/nginx/sites-available/boardinsight`): serve `frontend/dist` com fallback SPA para
`index.html`, cache longa em `/assets/`, e encaminha `/api/`, `/health` e `/ready` para `127.0.0.1:8000`.

## Pré-requisitos

```bash
sudo apt install python3 python3-venv rsync nginx curl nodejs npm
python3 --version        # 3.13.x
node --version           # ≥ 20.19 (Vite 8); o nodejs do Debian 13 serve
/opt/mongodb44/bin/mongod --version
```

Base de dados e utilizador MongoDB com `readWrite` só na base `BoardInsight` (ver Hardening do MongoDB).

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

## Hardening do MongoDB e firewall

Sem backups nem restauro (decisão): os dados são recolhidos de novo da API Businessmap.

| Medida | Onde |
|---|---|
| Autenticação (`security.authorization: enabled`) | `deploy/mongodb/mongodb44.conf` → `/etc/mongodb44.conf` |
| Só loopback (`net.bindIp: 127.0.0.1`) | idem |
| Cache WiredTiger 0,25 GB, `javascriptEnabled: false` | idem |
| Rotação do `mongod.log` (semanal, 20 MB, 4 cópias; `logRotate: reopen` + SIGUSR1) | `deploy/mongodb/logrotate-mongodb44` |
| Utilizador da app só com `readWrite` em `BoardInsight` | `deploy/mongodb/create-app-user.js` (password pedida no terminal) |
| UFW: entradas negadas por omissão; SSH e HTTP 80 só da LAN; 27017 e 8000 negadas | `deploy/mongodb/harden.sh` |

```bash
sudo deploy/mongodb/harden.sh                 # LAN detetada pela rota (ex.: 192.168.1.0/24)
sudo deploy/mongodb/harden.sh --lan 192.168.1.0/24 --no-firewall
cd /opt/boardinsight/backend && sudo -u boardinsight BOARDINSIGHT_ENV_FILE=/opt/boardinsight/.env \
  .venv/bin/python -m app.ops.check_mongodb  # só leitura; sai com 1 se houver FALHA
```

O `harden.sh` guarda a config anterior em `/etc/mongodb44.conf.bak.<data>`, só reinicia o MongoDB se a config mudou
e só acrescenta regras UFW (não faz reset). Atenção: com `default deny incoming`, outros serviços da máquina expostos na
LAN (ex.: portas 5173/5175) precisam de regra própria. O `check_mongodb` verifica sockets em LISTEN, a config,
que uma ligação sem credenciais é recusada e que o utilizador da app não tem roles fora de `read`/`readWrite` na base.

## Verificação

```bash
systemctl status businessmap-api businessmap-worker businessmap-sync.timer
systemctl list-timers businessmap-sync.timer
curl -s http://127.0.0.1/health            # {"status":"ok"}
curl -s http://127.0.0.1/ready             # 200 com mongodb e businessmap_api_key ok
journalctl -u 'businessmap-*' -n 50 -o cat # logs JSON, sem segredos
```

Depois de um reboot os serviços e o timer arrancam sozinhos (testes de aceitação em G4).
