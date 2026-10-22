# Businessmap Analytics — Especificação de Desenvolvimento

**Versão:** 1.0  
**Data:** 21-10-2026  
**Tipo:** Novo projeto independente (não reutilizar TeamForge)  
**Objetivo:** Portal interno de leitura e análise de boards Businessmap, com dashboards, relatórios e exportações.

---

## 1. Contexto e decisões

Construir um **site novo**, com repositório, frontend, backend e base de dados próprios. O site será executado num PC Linux Debian antigo, na rede local, com **MongoDB 4.4** (não atualizar para MongoDB 5+ devido às limitações do hardware). O **backend é obrigatoriamente Python**. A aplicação consulta a API REST V2 do Businessmap com permissões de leitura e permite escolher boards pelo respetivo ID.

### Configuração inicial validada

- Instância: `https://cttv8.kanbanize.com`
- Board inicial: **96**
- Workspace: **35**
- Nome do board: `Team Board: Channels | Physical Channels | Nave`
- Endpoint de leitura já testado: `GET /api/v2/boards?board_ids=96`
- Resultado: o utilizador confirmou acesso à API a partir de Windows e Debian.
- **Não incluir a API Key no repositório, nos logs, nos exemplos ou no frontend.**

### Âmbito

- **Incluído:** ligação segura, configuração de vários boards, importação e sincronização de dados, pesquisa, filtros, dashboards, relatórios, exportação e histórico.
- **Excluído do MVP:** criação, alteração, movimentação ou eliminação de cartões no Businessmap; integração com GitHub; reutilização do código TeamForge.
- **Importante:** o acesso ao endpoint de metadados do board **não comprova ainda** acesso a todos os endpoints de cartões, eventos, histórico ou bloqueios. Confirmar esses recursos antes de implementar métricas dependentes deles.

## 2. Stack técnica

| Camada | Tecnologia | Justificação |
|---|---|---|
| SO | Debian Linux | Execução local e gestão via systemd |
| Frontend | React + TypeScript + Vite | SPA com dashboards e filtros |
| UI | Tailwind CSS + biblioteca de componentes acessível | Interface responsiva |
| Gráficos | Recharts | Séries temporais, barras, linhas e distribuições |
| Backend | Python 3 + FastAPI | REST, OpenAPI, validação e execução eficiente |
| Validação | Pydantic | DTOs e configurações tipadas |
| HTTP externo | httpx | Timeouts, ligações persistentes e controlo de erros |
| MongoDB | **4.4.x** | Compatível com o PC; manter versão instalada |
| Driver Mongo | PyMongo compatível com MongoDB 4.4 | Fixar e testar versões; não assumir suporte de versões futuras |
| Jobs | APScheduler ou serviço Python dedicado | Sincronizações agendadas sem depender de requests web |
| Servidor Python | Uvicorn | ASGI |
| Reverse proxy | Nginx | Servir frontend e encaminhar `/api/` |
| Exportações | CSV/JSON, openpyxl, ReportLab | CSV, JSON, XLSX e PDF |
| Testes | pytest + httpx; Vitest | Backend e frontend |

**Compatibilidade obrigatória:** confirmar a versão de Python disponível no Debian e fixar versões de dependências suportadas; o MongoDB 4.4 está fora de suporte do fabricante, pelo que deve ficar isolado na rede interna, com autenticação, firewall e backups. O hardware antigo poderá não suportar AVX; manter o binário 4.4 já funcional e não propor upgrades incompatíveis.

## 3. Arquitetura

```text
Browser na LAN
    |
    v
Nginx :80/:443
    |-- /             -> frontend React compilado (ficheiros estáticos)
    `-- /api/*        -> FastAPI / Uvicorn em 127.0.0.1:8000
                               |
                               |-- BusinessmapClient (HTTPS, API Key)
                               |-- BoardService / CardService
                               |-- SyncService / Scheduler
                               |-- MetricsService / ReportService
                               `-- MongoDB 4.4 em 127.0.0.1:27017
```

- O browser **nunca** comunica diretamente com a API Businessmap nem recebe a API Key.
- MongoDB acessível apenas por loopback, salvo necessidade explícita e controlada.
- Frontend e backend com deployment independente, no mesmo servidor Linux.
- Leituras do dashboard devem privilegiar dados sincronizados; opcionalmente permitir atualização manual.
- Sincronizações não devem bloquear pedidos HTTP do utilizador.

## 4. Organização do repositório

```text
businessmap-analytics/
├── README.md
├── .gitignore
├── .env.example
├── docs/
│   ├── architecture.md
│   ├── businessmap-api-validation.md
│   ├── metrics-definitions.md
│   └── deployment-debian.md
├── backend/
│   ├── pyproject.toml
│   ├── requirements.lock
│   ├── app/
│   │   ├── main.py
│   │   ├── core/              # settings, security, logging
│   │   ├── api/v1/            # routers
│   │   ├── models/            # Pydantic schemas
│   │   ├── repositories/      # MongoDB
│   │   ├── integrations/      # BusinessmapClient
│   │   ├── services/          # boards, cards, metrics, reports
│   │   └── jobs/              # scheduler/sync
│   └── tests/
├── frontend/
│   ├── package.json
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   ├── charts/
│   │   ├── api/
│   │   ├── hooks/
│   │   └── types/
│   └── vite.config.ts
└── deploy/
    ├── nginx.conf
    ├── businessmap-api.service
    ├── businessmap-sync.service
    └── businessmap-sync.timer
```

## 5. Páginas e funcionalidades

### 5.1. Boards

- Adicionar board pelo ID numérico; consultar e validar metadados via API.
- Guardar ID, workspace, nome, estado e data da última sincronização.
- Lista de boards configurados, pesquisa e seleção do board ativo.
- Testar conectividade e permissões de leitura por board.
- Desativar sincronização sem apagar histórico; eliminar configuração mediante confirmação.

### 5.2. Dashboard geral

- Cartões totais, ativos, concluídos, bloqueados e vencidos (conforme dados disponíveis).
- Distribuição por coluna, lane, tipo, prioridade e responsável.
- Evolução de conclusões e criação de cartões por período.
- Filtros globais: board, intervalo de datas, developer, tipo, prioridade e estado.
- Indicadores com data de referência e aviso de dados desatualizados.

### 5.3. Cartões

- Tabela paginada, ordenável e pesquisável.
- Campos: ID, título, board, coluna/lane, responsável, prioridade, tipo, datas e URL de origem.
- Detalhe do cartão em modo leitura, com histórico quando disponível.
- Filtros combinados e exportação dos resultados filtrados.

### 5.4. Developers

- Distribuição de cartões por responsável e estado.
- Cartões concluídos por período, WIP por responsável e itens envelhecidos.
- Não tratar contagem de cartões como avaliação individual de desempenho; considerar complexidade e contexto.

### 5.5. Flow Analytics

- Throughput, WIP, Aging WIP, Lead Time, Cycle Time e percentis (P50/P85/P95).
- Cumulative Flow Diagram (CFD) quando houver histórico suficiente.
- Gráficos de tendência, comparação entre períodos e filtros.
- Explicitar a definição de início/fim e os estados mapeados para cada board.

### 5.6. Bloqueios e qualidade

- Cartões atualmente bloqueados, duração e causas (se disponibilizadas).
- Bugs por estado, severidade ou tipo (se esses campos existirem).
- Reaberturas e retrabalho apenas com histórico de transições.

### 5.7. Scrum / períodos

- Relatórios por sprint **apenas se houver identificação fiável de sprint** (campo, tag, data ou integração específica).
- Compromisso versus conclusão, burndown e velocity **apenas se existirem snapshots de compromisso e estimativas consistentes**.
- Se o board não usar sprints, apresentar métricas de fluxo em vez de inventar dados Scrum.

### 5.8. Reports

- Catálogo de relatórios: geral, por developer, fluxo, prazos, bloqueios, qualidade e comparação de boards.
- Filtros, visualização prévia, geração e download em CSV, JSON, XLSX e PDF.
- Guardar definições de relatórios (nome, filtros, gráficos e colunas), não apenas ficheiros.
- Relatório executivo semanal e mensal, opcionalmente gerado por agendamento.

### 5.9. Administração

- Estado da ligação Businessmap, última sincronização, duração, erros e volumes.
- Configuração de cadência, retenção, mapeamento de colunas e política de exportação.
- Gestão de utilizadores e acesso à aplicação, caso existam vários utilizadores.

## 6. Catálogo de relatórios e dependências

| Relatório | Indicadores | Dados necessários |
|---|---|---|
| Estado atual | Contagens por coluna, tipo e responsável | Cartões atuais |
| Entregas | Throughput diário/semanal/mensal | Datas fiáveis de conclusão |
| Prazos | Vencidos, próximos do prazo | Due date + estado |
| Aging WIP | Idade de cartões ativos | Data de entrada em progresso |
| Cycle Time | Média, mediana, P85/P95 | Transições início -> fim |
| Lead Time | Média, mediana, P85/P95 | Evento de entrada/criação -> fim |
| CFD | Volume por estado ao longo do tempo | Histórico ou snapshots periódicos |
| Bloqueios | Quantidade e duração | Eventos de bloqueio/desbloqueio |
| Reaberturas | Número e frequência | Histórico de transições |
| Scrum | Burndown, velocity, compromisso | Sprint + snapshots + estimativas |
| Comparativo | Variação entre boards/períodos | Definições de estados normalizadas |

**Regra de integridade:** não calcular durações históricas com base apenas na coluna atual. Snapshots iniciados hoje não permitem reconstruir o passado; apresentar a data de início da recolha.

## 7. Integração com a API Businessmap

### 7.1. Conectividade já validada

```http
GET https://cttv8.kanbanize.com/api/v2/boards?board_ids=96
apikey: <SEGREDO>
Accept: application/json
```

Resposta confirmada com `board_id=96`, `workspace_id=35` e nome do board.

### 7.2. Validação obrigatória antes de desenvolver o importador

1. Consultar o OpenAPI da instância `https://cttv8.kanbanize.com/openapi`.
2. Identificar endpoints efetivos de cartões, paginação, filtros, colunas, lanes, utilizadores e eventos/histórico.
3. Executar pedidos **GET** de teste ao Board 96, guardar amostras anonimizadas e documentar respostas reais.
4. Confirmar rate limits, paginação, erros e permissões de cada endpoint.
5. Mapear campos Businessmap -> modelos internos sem pressupor nomes de propriedades.
6. Só depois implementar importação incremental e métricas históricas.

**Nota:** os endpoints de cartões e histórico não são inventados nesta especificação; deverão ser preenchidos a partir da documentação real da instância.

### 7.3. BusinessmapClient Python

- Cliente `httpx.AsyncClient` com `base_url`, `timeout` e header `apikey` lido de variável de ambiente.
- Métodos separados: `get_boards`, `get_board`, `list_cards`, `get_card_details`, `get_history` (os últimos conforme endpoints confirmados).
- Retry com backoff exponencial para falhas transitórias/429/5xx, respeitando `Retry-After`.
- Nunca repetir automaticamente operações não idempotentes (embora o MVP seja apenas leitura).
- Erros normalizados: autenticação, permissão, não encontrado, rate limit, indisponibilidade e formato inesperado.
- Logs estruturados com `request_id`, duração, board ID e estado HTTP; **sem chave, tokens ou dados sensíveis**.

## 8. Modelo MongoDB 4.4

Base de dados sugerida: `businessmap_analytics`.

### Collections

| Collection | Finalidade | Índices sugeridos |
|---|---|---|
| `boards` | Configuração e metadados | `boardId` unique; `workspaceId` |
| `cards` | Estado atual dos cartões | `(boardId, cardId)` unique; `(boardId, status)`; `(boardId, assigneeId)` |
| `card_events` | Transições e eventos disponíveis | `(boardId, cardId, occurredAt)`; identificador externo único se existir |
| `board_snapshots` | Contagens por estado/instante | `(boardId, capturedAt)` unique |
| `sync_runs` | Auditoria de sincronizações | `(boardId, startedAt)` |
| `report_definitions` | Configurações de relatórios | `ownerId`, `name` |
| `report_exports` | Metadados de ficheiros exportados | `createdAt`, `expiresAt` |
| `users` | Acesso local, se necessário | `username` unique |

### Exemplo `boards`

```json
{
  "boardId": 96,
  "workspaceId": 35,
  "name": "Team Board: Channels | Physical Channels | Nave",
  "enabled": true,
  "syncIntervalMinutes": 15,
  "lastSuccessfulSyncAt": null,
  "stateMapping": {
    "todo": [],
    "inProgress": [],
    "done": []
  }
}
```

### Exemplo `cards` (modelo interno ilustrativo)

```json
{
  "boardId": 96,
  "cardId": "12345",
  "title": "Exemplo de tarefa",
  "assigneeId": null,
  "columnId": null,
  "status": "unknown",
  "createdAt": null,
  "completedAt": null,
  "lastSeenAt": "2026-10-21T20:00:00Z",
  "raw": {}
}
```

- `raw` contém apenas os campos externos necessários, sujeitos a política de retenção.
- Normalizar datas em UTC e guardar metadados de timezone para apresentação.
- Utilizar **upserts idempotentes** para cartões e deduplicação para eventos.
- Evitar coleções temporárias sem TTL e crescimento indefinido; estabelecer retenção para snapshots e logs.
- Para `sync_runs`, guardar contagens, cursores, duração, erros e estado, sem credenciais.

## 9. Sincronização e consistência

**Estratégia inicial:** sincronização completa paginada por board, com intervalo configurável (por exemplo, 15 minutos). Evoluir para incremental apenas se a API suportar filtros/cursor fiáveis.

1. Adquirir lock por board para impedir execuções concorrentes.
2. Registar `sync_run` em execução.
3. Ler todas as páginas da API, validando integridade e duplicados.
4. Aplicar upserts em `cards` e guardar eventos/snapshots quando disponíveis.
5. **Não marcar cartões como removidos ou concluídos se a sincronização for parcial/falhar.**
6. Atualizar `lastSuccessfulSyncAt` apenas após terminar todas as páginas.
7. Libertar lock e registar métricas/erros.

O frontend mostra `última sincronização`, `dados desatualizados` e estado do job. A atualização manual enfileira um job e devolve identificador de execução, em vez de esperar no pedido HTTP.

## 10. API REST interna — FastAPI

Prefixo: `/api/v1`.

| Método | Endpoint | Função |
|---|---|---|
| GET | `/health` | Liveness |
| GET | `/ready` | MongoDB/configuração pronta |
| GET | `/api/v1/boards` | Boards configurados |
| POST | `/api/v1/boards` | Adicionar board por ID (apenas configuração local) |
| GET | `/api/v1/boards/{board_id}` | Metadados |
| POST | `/api/v1/boards/{board_id}/test-connection` | Testar leitura externa |
| POST | `/api/v1/boards/{board_id}/sync` | Enfileirar sincronização |
| GET | `/api/v1/boards/{board_id}/sync-runs` | Histórico de sincronização |
| GET | `/api/v1/boards/{board_id}/cards` | Cartões, filtros e paginação |
| GET | `/api/v1/boards/{board_id}/dashboard` | KPIs atuais |
| GET | `/api/v1/boards/{board_id}/metrics/throughput` | Entregas por período |
| GET | `/api/v1/boards/{board_id}/metrics/cycle-time` | Cycle Time, se calculável |
| GET | `/api/v1/boards/{board_id}/metrics/wip` | WIP e aging |
| GET | `/api/v1/reports` | Definições de relatórios |
| POST | `/api/v1/reports` | Guardar definição |
| POST | `/api/v1/reports/export` | Gerar exportação |
| GET | `/api/v1/reports/exports/{export_id}` | Estado/download autorizado |

Paginação obrigatória para listas; filtros com validação; datas ISO 8601; respostas de erro padronizadas; limites de exportação e timeout de jobs.

## 11. Segurança

- `.env` no backend com permissões `chmod 600`; serviço com utilizador Linux dedicado.
- `BUSINESSMAP_API_KEY` nunca enviada ao frontend, commitada ou registada em logs.
- API apenas de leitura relativamente ao Businessmap; permissões de escrita locais restringidas por autenticação.
- Nginx a escutar na LAN, firewall a permitir apenas a sub-rede autorizada.
- Considerar HTTPS interno se houver credenciais ou vários utilizadores.
- MongoDB com autenticação e bind em `127.0.0.1`; backups cifrados e restauro testado.
- CORS restrito à origem do site; proteção contra injeções e validação de parâmetros.
- Rate limit nos endpoints locais de sincronização/exportação.
- Revisão de confidencialidade: títulos e descrições dos cartões podem conter dados internos.

## 12. Configuração `.env.example`

```dotenv
APP_ENV=production
APP_HOST=127.0.0.1
APP_PORT=8000
APP_LOG_LEVEL=INFO

MONGODB_URI=mongodb://businessmap_app:ALTERAR_PASSWORD@127.0.0.1:27017/businessmap_analytics?authSource=businessmap_analytics
MONGODB_DATABASE=businessmap_analytics

BUSINESSMAP_BASE_URL=https://cttv8.kanbanize.com
BUSINESSMAP_API_KEY=COLOCAR_APENAS_NO_ENV_REAL
BUSINESSMAP_BOARD_ID=96
BUSINESSMAP_TIMEOUT_SECONDS=30
SYNC_INTERVAL_MINUTES=15

EXPORT_DIR=/var/lib/businessmap-analytics/exports
EXPORT_RETENTION_DAYS=30
```

Nunca incluir `.env` real no Git; usar `.env.example` apenas com valores fictícios. URL/credenciais MongoDB são exemplos e deverão ser adaptados à instalação existente.

## 13. Deploy Debian

### Estrutura de instalação sugerida

```text
/opt/businessmap-analytics/
    backend/                 # código Python + venv
    frontend/dist/           # build React
/etc/businessmap-analytics/
    backend.env              # segredos (chmod 600)
/var/lib/businessmap-analytics/
    exports/                 # relatórios
/var/log/businessmap-analytics/
    (opcional; preferir journald)
```

### Procedimento

1. Confirmar arquitetura CPU, RAM, espaço livre, Python e MongoDB 4.4 em funcionamento.
2. Criar utilizador de sistema dedicado sem login e diretórios com permissões mínimas.
3. Criar base de dados e utilizador MongoDB com permissões `readWrite` apenas na base da aplicação.
4. Instalar Python compatível e ambiente virtual; instalar dependências com versões fixadas.
5. Criar `backend.env` fora do repositório e validar acesso ao Board 96.
6. Criar build de produção do React; pode ser compilado noutra máquina se o Debian tiver poucos recursos.
7. Configurar `systemd` para API e job de sincronização (timer/serviço separados).
8. Configurar Nginx para servir SPA e fazer proxy de `/api/` para `127.0.0.1:8000`.
9. Configurar firewall, rotação/retenção de logs, backups e reinício automático.
10. Testar `/health`, `/ready`, login, sincronização e relatórios após reboot.

### Exemplo conceptual de comandos

```bash
sudo mkdir -p /opt/businessmap-analytics /etc/businessmap-analytics /var/lib/businessmap-analytics/exports
python3 --version
mongod --version
# Executar instalação e configuração com utilizador de serviço dedicado.
# Não expor MongoDB na rede nem usar a API Key na linha de comandos.
```

## 14. Performance no PC antigo

- Limitar concorrência e workers Uvicorn conforme CPU/RAM medidos (começar com 1 worker).
- Agregar métricas no backend e usar índices adequados em MongoDB 4.4.
- Paginar tabelas e limitar séries temporais/intervalos de consulta.
- Cachear agregações frequentes por board/período e invalidar após sincronização.
- Não gerar relatórios PDF pesados durante o pedido HTTP; usar job e download posterior.
- Evitar processos duplicados de scheduler quando houver múltiplos workers.
- Testar com volumes reais antes de definir intervalo final de sincronização.

## 15. Testes e critérios de aceitação

### Integração

- Board 96 validado por GET; sem exposição da API Key.
- Importação completa paginada de cartões, após validação do endpoint real.
- Tratamento de HTTP 401, 403, 404, 429, 5xx, timeout e payload inesperado.
- Reexecução idempotente; falhas parciais não alteram indevidamente o estado dos cartões.

### Funcionais

- Adicionar board por ID e consultar metadados.
- Dashboard com contagens coerentes com o snapshot mais recente.
- Filtrar cartões por estado, responsável e período.
- Gerar CSV/JSON/XLSX/PDF e descarregar ficheiros autorizados.
- Métricas indisponíveis mostram motivo (por exemplo, histórico insuficiente), não zero fictício.

### Operacionais

- Serviços arrancam após reboot.
- MongoDB 4.4 mantém-se funcional no hardware existente.
- Backups e restauro testados.
- Aplicação acessível apenas a utilizadores da rede autorizada.
- Logs não contêm credenciais.

## 16. Roadmap de implementação

| Fase | Entregáveis | Critério de conclusão |
|---|---|---|
| 0 — Descoberta | Validar OpenAPI de cartões/histórico, exemplos reais, campos e limites | Matriz de campos/endpoints confirmada |
| 1 — Fundação | Novo repo, FastAPI, React, MongoDB 4.4, configuração e deploy base | Site e API funcionam no Debian |
| 2 — Boards e cartões | Adicionar board, cliente Businessmap, importador paginado, tabela de cartões | Board 96 sincroniza sem erros |
| 3 — Dashboards básicos | Contagens, filtros, throughput e prazos | Indicadores validados contra dados fonte |
| 4 — Histórico e flow | Eventos/snapshots, WIP, aging, cycle/lead time, CFD | Métricas apenas com dados suficientes |
| 5 — Reports e operação | Exportação, relatórios guardados, jobs, logs, backups, segurança | Operação estável após reboot |
| 6 — Evolução | Comparação de boards, relatórios agendados, permissões refinadas | Funcionalidades aprovadas pela equipa |

## 17. Ordem prática de desenvolvimento (primeiros tickets)

1. Criar repositório **novo** e scaffolding frontend/backend.
2. Criar configuração Pydantic e gestão segura da API Key.
3. Implementar `BusinessmapClient.get_boards()` e teste automático do Board 96.
4. Validar no OpenAPI os endpoints reais de cartões, campos e paginação.
5. Criar DTOs de cartões baseados nas respostas reais.
6. Criar collections/índices MongoDB 4.4 e repositórios Python.
7. Implementar sincronização idempotente, logs e estados de execução.
8. Implementar página Boards e tabela de Cartões.
9. Implementar Dashboard básico e testes de consistência.
10. Adicionar métricas históricas e exportações de forma incremental.

## 18. Riscos e decisões pendentes

| Risco / decisão | Mitigação |
|---|---|
| MongoDB 4.4 fora de suporte | Isolar na LAN, autenticar, firewall, backups; aceitar risco explicitamente |
| Endpoint de histórico indisponível | Começar snapshots agora; não prometer métricas históricas retroativas |
| API com limites de tráfego | Paginação, backoff, cache e sincronização controlada |
| Campos diferentes entre boards | Mapeamento configurável e validação por board |
| Hardware limitado | 1 worker inicial, jobs separados, consultas indexadas, build externo |
| Vários utilizadores | Autenticação local/reverse proxy e perfis de acesso |
| Dados internos confidenciais | Política de retenção e acesso restrito a relatórios |
| Sem definição uniforme de Done | Configuração explícita de colunas/estados por board |

## 19. Definição de concluído do MVP

O MVP está concluído quando o novo site, independente do TeamForge, corre no Debian, utiliza FastAPI e MongoDB 4.4, autentica com segurança na API Businessmap, permite adicionar o Board 96 pelo ID, sincroniza cartões com paginação, mostra dashboards básicos e exporta pelo menos CSV e JSON. Métricas avançadas só entram no MVP se os dados necessários forem confirmados durante a fase de descoberta.

---

**Nota final:** esta especificação define o desenvolvimento a executar; não afirma que os endpoints de cartões ou histórico já foram testados. A primeira tarefa técnica é validar esses endpoints na documentação OpenAPI da instância antes de implementar os relatórios avançados.

## 20. Desenvolvimento local (BoardInsight)

A documentação viva está em `.maestru/docs/` (`architecture`, `businessmap-api-validation`,
`metrics-definitions`, `deployment-debian`); os work-items em `.maestru/tracks/`.

```bash
cp .env.example .env && chmod 600 .env        # preencher MongoDB e BUSINESSMAP_API_KEY
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.lock && .venv/bin/pip install --no-deps -e .
.venv/bin/uvicorn app.main:app --port 8000     # API em http://127.0.0.1:8000/api/docs
cd ../frontend && npm ci && npm run dev         # UI em http://127.0.0.1:5180 (proxy para a API)
scripts/test.sh                                 # testes backend + frontend
```
