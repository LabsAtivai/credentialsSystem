# Snov Account Manager

Sistema interno de gerenciamento centralizado das contas Snov.io utilizadas pelos sistemas internos da empresa. Substitui a planilha atual como fonte de verdade: cadastro, edição, ativação/desativação, busca, controle de acesso por papel, auditoria e API para consumo por outros sistemas internos.

## Arquitetura

```
                    ┌─────────────────────┐
                    │     Admin UI        │
                    │   Vue 3 + TypeScript │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │       API           │
                    │ FastAPI + SQLAlchemy │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
        ┌──────────┐     ┌──────────┐    ┌──────────┐
        │ Sistema  │     │ Sistema  │    │ Sistema  │
        │ Interno  │     │ SDR      │    │ Automação│
        └──────────┘     └──────────┘    └──────────┘
                               │
                               ▼
                       ┌───────────────┐
                       │  PostgreSQL   │
                       └───────────────┘
```

**Stack:**

- Backend: Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic, PostgreSQL
- Frontend: Vue 3, TypeScript, Vite
- Auth: JWT (usuários humanos) + API keys com scopes (sistemas internos)
- Criptografia: AES-256-GCM (`cryptography`), hash de senha Argon2id (`pwdlib`)
- Infra: Docker Compose

## Estrutura de pastas

```
credenciais/
├── backend/
│   ├── app/
│   │   ├── main.py            # app FastAPI, middlewares, rotas
│   │   ├── config.py          # Settings (env vars), fail-fast na ausência de ENCRYPTION_KEY
│   │   ├── db/                # engine, sessão, Base declarativa
│   │   ├── models/             # SnovAccount, User, ApiKey, AuditLog
│   │   ├── schemas/            # DTOs Pydantic (separação admin vs credenciais)
│   │   ├── services/
│   │   │   ├── encryption.py  # EncryptionService (AES-256-GCM)
│   │   │   └── audit.py        # AuditService (bloqueia segredo em metadata)
│   │   ├── core/
│   │   │   ├── security.py    # JWT, Argon2id, geração de API key
│   │   │   └── rate_limit.py  # instância do Limiter (slowapi)
│   │   ├── api/v1/              # routers: auth, users, accounts, internal, api_keys, audit
│   │   ├── importer/           # importador CSV (dry-run + persistência)
│   │   └── seed_admin.py       # bootstrap do primeiro usuário ADMIN
│   ├── alembic/                # migrations versionadas
│   ├── tests/                  # pytest (unit + integração contra Postgres real)
│   ├── entrypoint.sh           # roda migrations e sobe o uvicorn
│   └── Dockerfile
├── frontend/
│   └── src/
│       ├── views/               # LoginView, AccountsView
│       ├── components/          # AccountFormModal, CredentialsModal, ConfirmDialog
│       ├── api/                  # client axios + chamadas tipadas
│       └── stores/auth.ts        # estado de autenticação (JWT em sessionStorage)
└── docker-compose.yml
```

## Instalação local (sem Docker)

### Backend

```bash
cd backend
python -m venv .venv
./.venv/Scripts/activate        # Windows (PowerShell: .venv\Scripts\Activate.ps1)
pip install -r requirements-dev.txt

cp .env.example .env
# preencher DATABASE_URL, JWT_SECRET e ENCRYPTION_KEY no .env (ver seção Variáveis de Ambiente)

alembic upgrade head
python -m app.seed_admin --name "Seu Nome" --email admin@empresa.com   # pede senha via prompt

uvicorn app.main:app --reload --port 8000
```

Docs interativas em `http://localhost:8000/docs` (Swagger, desabilitado automaticamente quando `ENVIRONMENT=production`).

### Frontend

```bash
cd frontend
npm install
cp .env.example .env   # ajustar VITE_API_URL se necessário
npm run dev
```

## Docker Compose

Sobe Postgres + API + frontend de uma vez, com migrations rodando automaticamente no start do backend.

```bash
cp .env.example .env
# preencher POSTGRES_PASSWORD, JWT_SECRET e ENCRYPTION_KEY

docker network create ativaai   # só se ainda não existir na máquina

docker compose up -d --build
docker compose exec -it snov-am-api python -m app.seed_admin --name "Seu Nome" --email admin@empresa.com
```

O Postgres **não** é exposto publicamente — só acessível pela rede Docker interna.

## Variáveis de ambiente

### `backend/.env`

| Variável | Descrição |
|---|---|
| `ENVIRONMENT` | `development` ou `production`. Em produção desabilita `/docs`, `/redoc`, `/openapi.json`. |
| `DATABASE_URL` | String de conexão PostgreSQL (`postgresql+psycopg://...`). |
| `JWT_SECRET` | Segredo de assinatura do JWT. |
| `JWT_ALGORITHM` | Default `HS256`. |
| `JWT_EXPIRES_MINUTES` | Expiração do token, default `60`. |
| `ENCRYPTION_KEY` | Base64 de 32 bytes (AES-256). **Obrigatória** — servidor recusa subir sem ela (fail-fast). Gerar com: `python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())"` |
| `CORS_ORIGINS` | Lista separada por vírgula das origens permitidas. |
| `API_RATE_LIMIT` | Limite default (formato slowapi, ex: `100/minute`). O endpoint de login tem limite próprio mais rígido (`10/minute`), fixo no código. |

### `frontend/.env`

| Variável | Descrição |
|---|---|
| `VITE_API_URL` | URL pública da API. Embutida no bundle em build-time (Vite) — mudar exige rebuild. |

### `.env` (raiz, usado pelo `docker-compose.yml`)

Combina as variáveis acima com `POSTGRES_PASSWORD`, `API_PORT` e `FRONTEND_PORT` (portas expostas no host).

**Nunca** commitar `.env` real — `.gitignore` já cobre `.env` e `.env.*`, mantendo só os `.env.example`.

## Banco de dados e migrations

Schema versionado via Alembic — nunca alterar o banco manualmente.

```bash
cd backend
alembic upgrade head              # aplica migrations pendentes
alembic revision --autogenerate -m "descrição"   # gera nova migration a partir dos models
alembic downgrade -1              # desfaz a última migration
```

Tabelas: `users`, `snov_accounts`, `api_keys`, `audit_logs`. Índices em `email`, `status`, `created_at` e no hash de lookup do `snov_email`. `snov_accounts` usa soft delete (`deleted_at`).

## Autenticação e autorização

**Usuários humanos** (login via `POST /api/auth/login`, retorna JWT):

| Role | Pode |
|---|---|
| `ADMIN` | Tudo: CRUD de contas, excluir, ativar/desativar, criar usuários, criar/revogar API keys, ver credenciais, consultar auditoria |
| `OPERATOR` | Criar, editar, ativar/desativar contas. Não vê credenciais nem exclui |
| `READONLY` | Só visualizar e pesquisar contas |

**Sistemas internos** (via `X-API-Key`, criada por um ADMIN em `POST /api/api-keys`): autorização por **scope**, não por role — cada chave recebe só os scopes necessários:

`accounts:read`, `accounts:write`, `accounts:delete`, `credentials:read`, `audit:read`

A chave completa só é exibida uma vez, na criação. O banco guarda apenas o hash (SHA-256) — perdeu, precisa gerar outra.

## Criptografia

`app/services/encryption.py` (`EncryptionService`) é o único lugar do sistema que lida com criptografia — AES-256-GCM, nonce aleatório de 12 bytes por operação (nunca reaproveitado), autenticação via tag do próprio GCM. Campos `snov_secret`, `snov_email` e `snov_password` ficam sempre como ciphertext no banco (`*_encrypted`).

`snov_email` também gera um HMAC-SHA256 determinístico (`snov_email_lookup_hash`) só pra checar duplicidade sem precisar do plaintext nem comparar ciphertext.

A `ENCRYPTION_KEY` **nunca** deve ir para o Git, `.env` commitado, logs ou backup do banco. Ver seção Backup.

## API — referência de endpoints

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| `POST` | `/api/auth/login` | — | Login, retorna JWT. Rate limit: 10/min por IP |
| `GET`/`POST` | `/api/users` | JWT ADMIN | Listar / criar usuários |
| `GET` | `/api/accounts` | JWT (qualquer role) | Lista paginada, busca por email, filtro por status |
| `GET` | `/api/accounts/{id}` | JWT (qualquer role) | Detalhe de uma conta |
| `POST` | `/api/accounts` | JWT ADMIN/OPERATOR | Cria conta (criptografa antes de salvar) |
| `PATCH` | `/api/accounts/{id}` | JWT ADMIN/OPERATOR | Edita conta |
| `DELETE` | `/api/accounts/{id}` | JWT ADMIN | Soft delete |
| `PATCH` | `/api/accounts/{id}/activate` | JWT ADMIN/OPERATOR | Ativa |
| `PATCH` | `/api/accounts/{id}/deactivate` | JWT ADMIN/OPERATOR | Desativa |
| `GET` | `/api/internal/accounts/{id}/credentials` | API key (`credentials:read`) ou JWT ADMIN | Retorna credenciais em plaintext (descriptografadas só em memória). Audita todo acesso |
| `GET`/`POST` | `/api/api-keys` | JWT ADMIN | Listar / criar API keys (chave completa só na criação) |
| `PATCH` | `/api/api-keys/{id}/revoke` | JWT ADMIN | Revoga uma API key |
| `GET` | `/api/audit-logs` | API key (`audit:read`) ou JWT ADMIN | Consulta auditoria, filtros por ação/recurso/usuário |
| `GET` | `/health` | — | Health check |

Nenhum endpoint fora de `/api/internal/.../credentials` retorna `snov_secret`, `snov_email` ou `snov_password`.

Docs interativas completas (Swagger/OpenAPI) em `/docs` — só disponível fora de produção.

## Importação da planilha atual

```bash
cd backend
python -m app.importer caminho/arquivo.csv --dry-run          # só analisa, não grava
python -m app.importer caminho/arquivo.csv                    # pede confirmação (digitar CONFIRM) antes de gravar
python -m app.importer caminho/arquivo.csv --yes               # pula a confirmação (uso em automação)
python -m app.importer caminho/arquivo.csv --actor-email admin@empresa.com  # associa a auditoria a um usuário
```

Aceita cabeçalhos `email, snov_id, snov_secret, snovemail, snovsenha` (e variações de maiúsculas/`description`/`descricao`). Detecta duplicado dentro do próprio arquivo, decide se cada linha é uma conta nova ou atualização de uma existente (por email ou `snov_email`), nunca imprime valor de campo sensível em erro, e uma linha inválida não trava as demais. Relatório final: total, válidos, inválidos, duplicados, novos, atualizados.

A planilha original **não** deve entrar no Git — `.gitignore` já bloqueia `*.csv`, `*.xlsx`, `*.xls`.

## Auditoria

Toda mutação de conta, criação/revogação de API key, login (sucesso e falha) e acesso a credenciais gera uma linha em `audit_logs`. `AuditService` bloqueia em tempo de gravação qualquer `metadata` que contenha chave sensível (`password`, `secret`, `token`, `jwt`, `api_key`, `encryption_key`, `snov_*`) ou valor com formato de JWT — lança exceção antes de persistir.

## Backup

**Banco de dados** e **chave de criptografia** são componentes separados e devem ser protegidos/versionados separadamente. Backup do banco sem a `ENCRYPTION_KEY` correspondente torna os campos `*_encrypted` irrecuperáveis — mantenha a chave em um cofre de segredos, nunca junto do dump do banco.

```bash
# dump do banco (dentro do container ou com acesso à rede docker)
docker compose exec snov-am-postgres pg_dump -U snov_user snov_account_manager > backup.sql
```

## Testes

```bash
cd backend
# subir um Postgres descartável e aplicar migrations antes:
docker run --rm -d --name snov-test-db -e POSTGRES_PASSWORD=test -e POSTGRES_DB=snov_test -p 55432:5432 postgres:16-alpine
export DATABASE_URL="postgresql+psycopg://postgres:test@localhost:55432/snov_test"
export JWT_SECRET="test-secret"
export ENCRYPTION_KEY=$(python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())")
alembic upgrade head

pytest tests/ -v
```

49 testes cobrindo: criptografia (roundtrip, adulteração, chave inválida), fail-fast de configuração, filtro de auditoria contra vazamento de segredo, CRUD de contas e garantia de que endpoints genéricos nunca retornam credenciais, controle de acesso por role e por scope de API key, endpoint de credenciais (scope, revogação, expiração, dual-auth ADMIN/API key), importador CSV (dry-run, duplicado, reimportação como atualização, erro não vaza valor sensível), rate limit do login, token JWT malformado.

## Segurança — resumo do que foi validado

- Senhas de usuário: Argon2id (irreversível). Credenciais Snov: AES-256-GCM (reversível, nonce único).
- Nenhum endpoint administrativo retorna `snov_secret`/`snov_email`/`snov_password`.
- Rate limit real (via `SlowAPIMiddleware`) — 10/min no login contra força bruta, 100/min default nas demais rotas.
- Timing attack de enumeração de usuário no login mitigado (hash dummy quando usuário não existe).
- Auditoria bloqueia valores sensíveis por nome de campo e por formato (JWT) antes de gravar.
- CORS restritivo via `CORS_ORIGINS`, nunca wildcard.
- Sem SQL cru em lugar nenhum — só ORM parametrizado.
- Swagger desabilitado em produção.
- `.gitignore`/`.gitattributes` cobrindo `.env`, planilhas, credenciais de terceiros e forçando LF em scripts shell (evita quebra do `entrypoint.sh` em container Linux por causa do `core.autocrlf` do Git no Windows).
