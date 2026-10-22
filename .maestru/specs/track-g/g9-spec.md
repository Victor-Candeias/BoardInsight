---
maestru: "0.4"
type: work-spec
id: g9-spec
title: "G9 — Autenticação LDAPS e API só em 127.0.0.1"
template: implementation-plan-v1
work-item: track-g/G9
owner: developer
created: 2026-10-22
---

# G9 — Autenticação LDAPS e API só em 127.0.0.1

## Overview

Cada PC Windows corre a sua instalação do BoardInsight. A API passa a escutar só em `127.0.0.1` e exige login com o
email e a password do domínio `w2k.ctt.pt`, validados no Active Directory por LDAPS. As questões à TI (UPN = email?,
DCs com LDAPS e CA, grupo, conta de serviço) continuam em aberto, por isso tudo o que depende delas é configurável.

### Decisões

| Decisão | Escolha | Motivo |
|---------|---------|--------|
| Ativação | `AUTH_ENABLED` (omissão `false`; `true` no `env.windows`) | Debian e desenvolvimento ficam como estavam |
| DCs | `LDAP_URL` (lista, failover com `ServerPool`) ou DNS SRV `_ldap._tcp.dc._msdcs.<domínio>`; sem SRV, `ldaps://<domínio>:636` | Funciona sem configuração num PC do domínio e permite fixar DCs |
| TLS | `ldaps://` ou `ldap://` + StartTLS obrigatório; `CERT_REQUIRED` e hostname verificado; CA de `LDAP_CA_FILE` ou do repositório do Windows | Nunca enviar a password sem TLS nem a um DC não autenticado |
| Login | Bind com o email como UPN; com `LDAP_BIND_USER` procura `mail`/`userPrincipalName` e faz bind com o DN | Cobre UPN = email e UPN diferente do email |
| Password vazia | Recusada antes do bind | No AD um bind com password vazia é "não autenticado" e é aceite |
| Grupo | `AUTH_ALLOWED_GROUP` (nome ou DN); pertença com `LDAP_MATCHING_RULE_IN_CHAIN`; vazio = qualquer utilizador do domínio | Inclui grupos aninhados; o nome do grupo ainda não é conhecido |
| Sessão | Token aleatório (`secrets.token_urlsafe(32)`) em cookie HttpOnly + SameSite=Strict; MongoDB `auth_sessions` com o SHA-256, expiração por inatividade (480 min, renovada no máx. 1×/min) e absoluta (24 h), índice TTL | Sem segredos locais; uma cópia da BD não dá sessões válidas |
| Rate limit | Só falhas (401) contam: `AUTH_MAX_FAILED_LOGINS` por email e por IP em 15 min → 429 | Evita bloquear contas no AD por tentativas repetidas |
| Erros | 401 `invalid_credentials`, 403 `forbidden`, 503 `directory_unavailable`, 429 `too_many_attempts` | Mensagens genéricas; causa do AD (`data 52e/775/532`) só no log |
| Bind | `prepare_env` força `APP_HOST=127.0.0.1` e acrescenta as chaves novas do modelo em atualizações; o instalador já não cria a regra de firewall e apaga a antiga | Atualizações de versões antigas ficam corretas sem editar o `.env` |

## Implementation

### Fase 1 — Backend

1. `core/config.py`: `AUTH_*`/`LDAP_*`, `ldap_search_base`, `LDAP_BIND_PASSWORD` como segredo (redigido nos logs).
2. `services/auth.py`: `LdapDirectory` (bind, pesquisa do utilizador, grupo), `ldap_server_urls` (config/DNS SRV),
   fábrica de ligações `ldap3` com TLS; exceções `InvalidCredentials`/`AccessDenied`/`DirectoryUnavailable`.
3. `repositories/auth_sessions.py` e índice TTL `auth_sessions.expiresAt_ttl` em `core/indexes.py`.
4. `api/rate_limit.py`: `check`/`record`/`reset` sem registo automático.
5. `api/v1/auth.py`: `login`, `logout`, `me` e a dependência `require_user`; `main.py` aplica-a a todo o `api_router`.
6. `requirements*.lock`: `ldap3==2.9.1`, `pyasn1==0.6.4` (pure Python, wheel `py3-none-any`).

### Fase 2 — Frontend

1. `api/auth.ts` e evento `boardinsight:unauthorized` em `api/client.ts` em qualquer 401 fora de `/auth/*`.
2. `components/AuthGate.tsx`: `AuthGate` (envolve as rotas em `App.tsx`), `LoginPage` e `UserMenu` (nome e
   "Terminar sessão" no cabeçalho do `Layout`). Após login, as queries são invalidadas; após logout, removidas.

### Fase 3 — Instalação Windows

1. `env.windows`: `APP_HOST=127.0.0.1`, bloco `AUTH_*`/`LDAP_*` com `AUTH_ENABLED=true` e `LDAP_DOMAIN=w2k.ctt.pt`.
2. `ops/windows_setup.py`: força `APP_HOST` e acrescenta chaves em falta.
3. `boardinsight.iss`: sem tarefa/regra de firewall; `RemoveFirewallRule` na instalação e na desinstalação.

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `backend/app/services/auth.py` | Create | Validação no AD por LDAPS |
| `backend/app/repositories/auth_sessions.py` | Create | Sessões (hash do token, expiração) |
| `backend/app/api/v1/auth.py` | Create | Endpoints e `require_user` |
| `backend/app/main.py`, `backend/app/core/config.py`, `backend/app/core/indexes.py`, `backend/app/api/rate_limit.py` | Modify | Ligação, definições, índice TTL, rate limit de falhas |
| `backend/app/ops/windows_setup.py` | Modify | `APP_HOST=127.0.0.1` e chaves novas no `.env` |
| `backend/requirements.lock`, `backend/requirements-dev.lock`, `backend/pyproject.toml` | Modify | `ldap3`, `pyasn1`, `dnspython` |
| `backend/tests/test_auth.py`, `backend/tests/test_windows_setup.py` | Create/Modify | Testes |
| `frontend/src/api/auth.ts`, `frontend/src/components/AuthGate.tsx` (+ teste) | Create | Login, sessão, menu do utilizador |
| `frontend/src/api/client.ts`, `frontend/src/App.tsx`, `frontend/src/components/Layout.tsx`, `frontend/src/test/utils.tsx`, `frontend/src/App.test.tsx` | Modify | Integração |
| `deploy/windows/env.windows`, `deploy/windows/boardinsight.iss`, `.env.example` | Modify | Instalação |
| `.maestru/docs/deployment-windows.md`, `.maestru/docs/architecture.md`, `README.md` | Modify | Documentação (revisão da decisão A3 no Windows) |

## Validação

- [x] `pytest` (backend completo), incluindo `test_auth.py`: LDAP simulado (bind, conta de serviço, grupo aninhado,
      escape de filtros, DC indisponível com o `ldap3` real), 401/403/429/503, cookie, logout, expiração, password fora
      dos logs e das respostas; `test_windows_setup.py`: `APP_HOST` e chaves novas na atualização.
- [x] Vitest (16 ficheiros, 42 testes), `npm run typecheck`, `npm run build`.
- [x] Backend real com `AUTH_ENABLED=true` (porta 8090): escuta só em `127.0.0.1`; `/health` 200; `/api/v1/boards` e
      `/auth/me` 401; login com DC inalcançável → 503 com mensagem de rede/VPN; ecrã de login verificado no Edge
      (claro e escuro).
- [ ] Login real num PC do domínio na rede da empresa (este PC não chega a nenhum DC: `nltest /dsgetdc` →
      `ERROR_NO_SUCH_DOMAIN`), instalação/atualização com o instalador e `netstat` só em `127.0.0.1`.
- [ ] Respostas da TI: UPN = email, DCs com LDAPS e CA, grupo autorizado, conta de serviço.
