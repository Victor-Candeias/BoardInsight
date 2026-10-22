---
maestru: "0.4"
type: work-spec
id: g8-spec
title: "G8 — App desktop WPF com WebView2"
template: implementation-plan-v1
work-item: track-g/G8
owner: developer
created: 2026-10-22
---

# G8 — App desktop WPF com WebView2

## Overview

Opção de menor esforço para ter o BoardInsight como app Windows: uma janela WPF com um controlo WebView2 (Edge/Chromium)
que carrega a SPA servida pela API local (`http://localhost:<porta>/`). A UI React, a API, o worker e o MongoDB não
mudam. O instalador G7 passa a incluir a app, os atalhos e o WebView2 Runtime.

### Decisões

| Decisão | Escolha | Motivo |
|---------|---------|--------|
| Framework | .NET Framework 4.7.2 (`net472`) | Vem com o Windows 10 1809+ (o mínimo do instalador); não obriga a instalar um runtime .NET nem a juntar ~45 MB de um self-contained .NET 8 |
| Build | `dotnet publish` com `EnableWindowsTargeting` e `Microsoft.NETFramework.ReferenceAssemblies` | Compila em Linux, dentro do `build-installer.sh` existente |
| URL | `--url` > `BOARDINSIGHT_URL` > `HKLM\SOFTWARE\BoardInsight\Url` > `http://localhost:8080/` | O `.env` em `%ProgramData%` só é legível por administradores; o instalador escreve a porta no registo |
| Navegação | Só a origem da app fica na janela; http/https/mailto externos vão para o browser predefinido; outros esquemas são bloqueados | Evita que a janela se torne um browser genérico |
| Arranque | Espera por `GET /health` (1 s, até 2 min, sem proxy) com ecrã de estado | Logo após o boot os serviços podem ainda não estar prontos |
| Dados do WebView2 | `%LOCALAPPDATA%\BoardInsight\WebView2` | `Program Files` não é gravável pelo utilizador |
| WebView2 Runtime | Verificado pela chave `pv` (HKLM 32 bits e HKCU); se faltar, o instalador descarrega o bootstrapper da Microsoft e instala em silêncio | Já vem no Windows 11 e na maioria dos Windows 10; a app explica como obtê-lo se faltar |
| Instância única | Mutex `BoardInsight.Desktop` (também `AppMutex` do Inno) | O instalador pede para fechar a app antes de atualizar |

## Implementation

### Fase 1 — App WPF

1. `desktop/BoardInsight.Desktop`: `App` (mutex, leitura do registo, erros não tratados), `MainWindow` (WebView2 e painel
   de estado com "Tentar novamente", "Obter o WebView2" e "Abrir no browser") e `DesktopSettings` (lógica pura).
2. Título da janela segue o `document.title`; `--devtools` ativa as ferramentas de programador.
3. Se o WebView2 falhar (`ProcessFailed`), mostra um erro; "Tentar novamente" recarrega a página ou, se o processo do
   browser terminou, reinicia a app. A falta de runtime mostra uma mensagem própria.
4. Ícone `BoardInsight.ico` gerado a partir de `images/BoardInsight.png` (16–256 px); logo partilhado com o frontend.

### Fase 2 — Testes

1. `desktop/BoardInsight.Desktop.Tests` (xUnit, `net8.0`) liga `DesktopSettings.cs` e cobre a prioridade do URL, a
   normalização (só a origem, só http/https), a mesma origem e os esquemas externos.

### Fase 3 — Build e instalador

1. `build-installer.sh`, passo 3: copia `desktop/` e `frontend/public/brand` para o stage, corre `dotnet publish` para
   `app/desktop` e copia o ícone para `setup/`. O `dotnet` vem do PATH ou de `~/.dotnet/dotnet`.
2. `boardinsight.iss`: `AppMutex`, `SetupIconFile`, tarefa `desktopicon`, valor `Url` no registo, atalhos da app, atalho
   "BoardInsight no browser.url", `EnsureWebView2` no fim do `PostInstall` e abertura da app no fim da instalação.

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `desktop/BoardInsight.Desktop/*` | Create | App WPF (projeto, `App`, `MainWindow`, `DesktopSettings`, ícone) |
| `desktop/BoardInsight.Desktop.Tests/*` | Create | Testes de `DesktopSettings` |
| `deploy/windows/build-installer.sh` | Modify | Compilar e incluir a app desktop |
| `deploy/windows/boardinsight.iss` | Modify | Atalhos, registo, WebView2 Runtime, abrir a app no fim |
| `.gitignore` | Modify | Ignorar `bin/` e `obj/` do .NET |
| `.maestru/docs/deployment-windows.md`, `.maestru/docs/architecture.md`, `README.md` | Modify | Documentação |

## Validação

- [x] `dotnet test desktop/BoardInsight.Desktop.Tests` (14 testes) no Windows e no Linux.
- [x] App compilada em Linux corre no Windows: ecrã de espera, recuperação automática quando a API arranca, SPA carregada.
- [x] `deploy/windows/build-installer.sh --skip-frontend` gera `dist/windows/BoardInsight-Setup-0.1.0.exe` com
      `app\desktop\BoardInsight.exe`.
- [ ] Instalação num Windows 10/11 real: atalhos, valor no registo, instalação do WebView2 Runtime quando falta,
      `AppMutex` na atualização.
