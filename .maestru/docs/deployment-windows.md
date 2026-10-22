---
maestru: "0.4"
type: doc
id: deployment-windows
title: Instalador Windows
created: 2026-10-22
description: "Instalador .exe autónomo para Windows (Python embutido, MongoDB, serviços WinSW) gerado em Linux: requisitos, instalação, operação e build."
owner: developer
tags: [deployment, operations, windows]
updated: 2026-10-22
---

# Instalador Windows

<!-- maestru:summary -->
<!-- /maestru:summary -->

Work-item G7 (spec `g7-spec`). Um único `BoardInsight-Setup-<versão>.exe` (cerca de 70 MB) instala tudo o que o BoardInsight
precisa. O PC Windows não precisa de ter Python, Node, MongoDB, Nginx nem .NET. HTTP na LAN, sem HTTPS nem autenticação
(mesma decisão do Debian, A3). Desde o G8 (spec `g8-spec`) inclui também a app desktop **BoardInsight** (WPF com
WebView2), que mostra a SPA numa janela própria.

## Requisitos do PC Windows

- Windows 10 1809 ou superior, ou Windows Server 2019 ou superior, de 64 bits (requisito do MongoDB 8.0).
- **CPU com AVX**. O MongoDB 5 e superiores não arranca sem AVX (erro `0xC000001D`, instrução ilegal). Os Atom, Celeron e
  Pentium Silver mais antigos não têm AVX. Verificar com o `Coreinfo -f` da Sysinternals ou na ficha do processador.
- 4 GB de RAM recomendados (cache do WiredTiger limitada a 1 GB) e cerca de 1 GB livre em disco, mais os dados.
- Conta de administrador para instalar.
- Porta do site livre (por omissão 8080) e porta 27018 livre em 127.0.0.1 (MongoDB interno; não colide com um MongoDB
  na 27017).
- Acesso HTTPS a `https://cttv8.kanbanize.com` e uma API key do Businessmap.

## O que fica instalado

| O quê | Onde |
|-------|------|
| Programa (Python 3.13 embutido, `backend\app`, `frontend\dist`, `mongod.exe`) | `C:\Program Files\BoardInsight` |
| Dados: `.env` (com a API key), `mongodb-admin.secret`, base de dados, exportações e logs | `%ProgramData%\BoardInsight` (ACL só para SYSTEM e Administradores) |
| Serviços WinSW, automáticos e com reinício em caso de falha | `boardinsight-mongodb`, `boardinsight-api` (API + site) e `boardinsight-worker` |
| Sincronização a cada 30 min (conta SYSTEM) | Tarefa agendada `BoardInsight\Sync` → `sync.cmd` |
| Regra de firewall (opcional, ativa por omissão) | `BoardInsight`: TCP na porta do site, perfis domínio e privado, só a sub-rede local |
| Microsoft Visual C++ Redistributable x64 (necessário ao `mongod.exe`) | Instalado em silêncio |
| App desktop `BoardInsight.exe` (WPF, .NET Framework 4.7.2, já incluído no Windows) | `C:\Program Files\BoardInsight\desktop`; atalhos no menu Iniciar e, opcionalmente, no ambiente de trabalho |
| URL usado pela app (`http://localhost:<porta>/`) | Registo `HKLM\SOFTWARE\BoardInsight`, valor `Url` |
| Microsoft Edge WebView2 Runtime (só se faltar; já vem no Windows 11) | Descarregado da Microsoft (`go.microsoft.com/fwlink/p/?LinkId=2124703`) e instalado em silêncio |
| Atalho "BoardInsight no browser" | Menu Iniciar |

No Windows não há Nginx: com `FRONTEND_DIST` definido, a própria API serve a SPA na mesma origem
(`backend/app/core/frontend.py`).

## Instalação

1. Correr `BoardInsight-Setup-<versão>.exe` como administrador.
2. A página **Ligação ao Businessmap** pede:
   - URL da instância (pré-preenchido com `https://cttv8.kanbanize.com`);
   - API key (campo mascarado);
   - board inicial (por omissão `96`);
   - porta do site (por omissão `8080`).
3. Ao carregar em Seguinte, o instalador valida a key com `GET /api/v2/boards?board_ids=<board>`. Se a validação
   falhar, pergunta se quer continuar (útil quando não há rede no momento).
4. No fim da instalação:
   - protege `%ProgramData%\BoardInsight`;
   - instala os serviços e arranca o MongoDB;
   - corre `python -m app.ops.windows_setup`, que gera o `.env`, cria o admin e o utilizador `boardinsight` do MongoDB
     (`--auth`), cria os índices e regista o board inicial com um job `sync_board`;
   - arranca a API e o worker;
   - cria a tarefa agendada e a regra de firewall;
   - instala o WebView2 Runtime, se faltar (sem rede só fica um aviso no log; a app explica como o obter).
5. A app BoardInsight abre no fim (exceto em modo silencioso). Também se pode abrir `http://localhost:8080/` no browser,
   ou `http://<ip-do-pc>:8080/` a partir da LAN.

A API key é passada ao `windows_setup` pela variável de ambiente `BOARDINSIGHT_SETUP_API_KEY` do processo. Nunca aparece
em argumentos nem em logs.

**Instalação silenciosa.** A key vem só da variável de ambiente, porque o Inno grava a linha de comandos no log:

```bat
set BOARDINSIGHT_SETUP_API_KEY=<api key>
BoardInsight-Setup-0.1.0.exe /VERYSILENT /SUPPRESSMSGBOXES /URL=https://cttv8.kanbanize.com /BOARD=96 /PORT=8080
```

Juntar `/TASKS=""` para não criar a regra de firewall nem o atalho no ambiente de trabalho (`/TASKS="firewall"` mantém a
firewall). Os códigos de saída e os avisos ficam no log do Inno
(`%TEMP%\Setup Log *.txt`) e em `%ProgramData%\BoardInsight\logs\setup.log`.

Códigos do `windows_setup`: 1 = falha no MongoDB; 2 = board inicial não registado (não fatal); 3 = falha a preparar o
`.env` ou o segredo do admin (por exemplo, uma pasta com conteúdo no lugar de `.env`). O instalador remove pastas
vazias que ocupem o lugar de `.env` ou de `logs\sync.log`.

## Atualização e desinstalação

- **Atualizar.** Correr o `.exe` da nova versão. Os campos vêm pré-preenchidos a partir do `.env` existente; deixar a API
  key em branco mantém a atual. O instalador para os serviços e a tarefa, substitui o programa e volta a configurar tudo.
  Os dados e as passwords do MongoDB mantêm-se.
- **Desinstalar.** Em Definições → Aplicações, ou com `unins000.exe`. Remove a tarefa, os serviços e a regra de firewall.
  No fim pergunta, com "Não" por omissão, se apaga também `%ProgramData%\BoardInsight` (base de dados, `.env` e API key).
  Em modo silencioso os dados nunca são apagados.

## Operação

- Logs em `%ProgramData%\BoardInsight\logs`:
  - `boardinsight-*.out.log`, `*.err.log` e `*.wrapper.log` (rodados a 10 MB, 5 ficheiros);
  - `sync.log`;
  - `setup.log`.
- Serviços:
  - `services.msc`;
  - ou `"C:\Program Files\BoardInsight\boardinsight-api.exe" restart|status`;
  - ou `sc query boardinsight-api`.
- Para mudar a configuração, editar `%ProgramData%\BoardInsight\.env` como administrador e reiniciar a API e o worker.
  Para mudar a porta, ajustar também a regra de firewall `BoardInsight`, ou correr de novo o instalador.
- Sincronização manual: `schtasks /Run /TN "BoardInsight\Sync"`, ou o botão Sincronizar na interface.
- Novos boards: página Boards (`POST /api/v1/boards`), como no Debian.

## App desktop (G8)

- Janela WPF com WebView2 que carrega a SPA de `http://localhost:<porta>/`. Só uma instância de cada vez.
- Enquanto a API não responde em `/health` (por exemplo logo após o arranque do Windows), mostra um ecrã de espera e
  tenta durante 2 minutos. Depois oferece "Tentar novamente" e "Abrir no browser".
- Links para outros sites e novas janelas abrem no browser predefinido.
- URL, por ordem: argumento `--url <url>`, variável `BOARDINSIGHT_URL`, registo `HKLM\SOFTWARE\BoardInsight\Url`,
  `http://localhost:8080/`. Pode apontar para outro PC da LAN (`BoardInsight.exe --url http://servidor:8080/`).
  `--devtools` ativa as ferramentas de programador.
- Dados do WebView2 (cache, armazenamento local) em `%LOCALAPPDATA%\BoardInsight\WebView2`, por utilizador.
- Sem WebView2 Runtime, a app mostra o botão "Obter o WebView2" (página da Microsoft).
- Testes: `dotnet test desktop/BoardInsight.Desktop.Tests`.

## Build (em Linux, sem root)

```bash
deploy/windows/build-installer.sh            # ou --skip-frontend para reutilizar frontend/dist
# -> dist/windows/BoardInsight-Setup-<versão>.exe (+ .sha256); versão = backend/app/__init__.py
```

- **Requisitos:** `python3` (3.13 para pré-compilar o bytecode) com `pip`, `npm`, `curl`, `tar` e `rsync`, e o
  **.NET SDK 8** (no PATH ou em `~/.dotnet`, por exemplo com `dotnet-install.sh --channel 8.0`) para compilar a app
  desktop. São precisos cerca de 3 GB livres na cache, sobretudo pelo ZIP do MongoDB (800 MB).
- **Processo:**
  - Descarrega e verifica (SHA256 de `deploy/windows/versions.env`):
    - Python 3.13 embeddable;
    - MongoDB 8.0 (do ZIP extrai só `mongod.exe` e `vc_redist.x64.exe`);
    - WinSW 2.12;
    - Inno Setup 6.7;
    - Wine 11.0 portátil (Kron4ek). Se existir um `wine` no sistema, usa esse.
  - Instala as dependências do `requirements.lock` como wheels `win_amd64`/cp313 (`pip --platform`), mais o `tzdata`.
  - Compila a app desktop (`desktop/BoardInsight.Desktop`) com `dotnet publish` para `app/desktop`. O WPF para
    `net472` compila em Linux graças a `EnableWindowsTargeting` e aos pacotes de reference assemblies.
  - Compila o `deploy/windows/boardinsight.iss` com o ISCC sob Wine, com o driver gráfico `null`, sem display. Demora
    cerca de 3 minutos num Atom.
- **Variáveis:**
  - `BOARDINSIGHT_BUILD_CACHE` (por omissão `~/.cache/boardinsight-windows-build`);
  - `WINE`, `WINEPREFIX` e `OUT_DIR`;
  - `KEEP_STAGE=1` para manter o stage e inspecionar o conteúdo.
- **Atualizar versões:** mudar a versão e o URL em `versions.env` e atualizar o SHA256 com `sha256sum` do ficheiro novo.
  Python e MongoDB só com teste completo.

## Validação

Feita sob Wine 11.0 neste Debian:
- O Python embutido importa a aplicação.
- O `windows_setup` funciona contra um MongoDB com `--auth`: cria os utilizadores, é idempotente e devolve o código 2
  com uma key inválida.
- A API serve a SPA, os assets e o 404 JSON em `/api`.
- O worker arranca.
- A instalação silenciosa completa instala os serviços WinSW (`%BASE%` e `%ProgramData%` expandidos), o ICACLS, o
  vc_redist e a firewall.
- A desinstalação preserva os dados.

Limites desta validação: o `mongod.exe` não corre aqui (Atom sem AVX) e o Wine não suporta `schtasks /Create`.
**Falta validar num Windows 10/11 real:** arranque do MongoDB com `--auth`, tarefa agendada, `stopwait` dos serviços e
acesso a partir da LAN.

App desktop (G8): a app compilada em Linux foi testada num Windows 11 contra um servidor de teste (ecrã de espera,
recuperação quando o servidor arranca, SPA carregada). Falta validar a instalação completa: atalhos, valor no registo,
instalação do WebView2 Runtime quando falta e o `AppMutex` numa atualização. O bootstrapper do WebView2 é descarregado
por HTTPS da Microsoft no momento da instalação, sem SHA256 fixo (o ficheiro muda com cada versão).
