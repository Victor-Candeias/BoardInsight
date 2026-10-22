---
maestru: "0.4"
type: work-track
id: track-g
title: Operação e segurança
created: 2026-10-21
description: Operação e segurança
owner: developer
status: active
---

# track-g: Operação e segurança

## Summary

<!-- maestru:summary -->
| ID | Title | Status | Created | Owner | Priority | Completed | Template | Blocked By | Spec |
|---|---|---|---|---|---|---|---|---|---|
| G1 | Deploy Debian: systemd, Nginx, utilizador dedicado, docs/deployment-debian.md | backlog | 2026-10-21 | developer | high |  |  | B1, B2 |  |
| G2 | Hardening MongoDB (auth, bind loopback, firewall LAN) e backups com restauro testado | backlog | 2026-10-21 | developer | high |  |  | G1 |  |
| G3 | Rate limit em sync/export e CORS restrito | backlog | 2026-10-21 | developer | medium |  |  | C4, F1 |  |
| G4 | Testes de aceitação operacionais (reboot, logs sem credenciais) | backlog | 2026-10-21 | developer | medium |  |  | G1 |  |
<!-- /maestru:summary -->

<!-- maestru:work-items-list -->
| ID | Title | Status | Created | Owner | Priority | Completed | Template | Blocked By | Spec |
|---|---|---|---|---|---|---|---|---|---|
| C8 | Deploy local em /opt/BoardInsight com systemd de utilizador | done | 2026-10-22 |  | medium | 2026-10-22 |  |  |  |
| G1 | Deploy Debian: systemd, Nginx, utilizador dedicado, docs/deployment-debian.md | done | 2026-10-21 | developer | high | 2026-10-22 |  | track-b/B1, track-b/B2 |  |
| G2 | Hardening MongoDB (auth, bind loopback, firewall LAN); sem backups | done | 2026-10-21 | developer | high | 2026-10-22 |  | G1 |  |
| G3 | Rate limit em sync/export e CORS restrito | done | 2026-10-21 | developer | medium | 2026-10-22 |  | track-c/C4, track-f/F1 |  |
| G4 | Testes de aceitação operacionais (reboot, logs sem credenciais) | done | 2026-10-21 | developer | medium | 2026-10-22 |  | G1 |  |
| G5 | Deploy local: units systemd de utilizador para worker de jobs e timer de sync | done | 2026-10-22 |  | high | 2026-10-22 |  |  |  |
<!-- /maestru:work-items-list -->
