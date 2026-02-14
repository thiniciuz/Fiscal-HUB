# Fiscal HUB

Plataforma para operacao fiscal com foco em controle de tarefas, competencias, anexos e acompanhamento por status.

## Visao do produto
O projeto centraliza a rotina fiscal de empresas em um painel unico, com fluxo de:
- login por perfil (`admin`, `manager`, `collab`)
- gestao de empresas
- criacao e acompanhamento de tarefas fiscais
- upload de PDF e verificacoes de inconsistencias
- notificacoes e comentarios internos
- relatorios por periodo e status

## Stack
- Frontend Web: React + Vite (`web/`)
- Backend API: FastAPI + SQLite (`server/`)
- Desktop: Tauri 2 (`desktop/`)
- Desktop alternativo (legado): PySide6 (`client/`)

## Funcionalidades principais
- Autenticacao com papeis e permissoes
- CRUD de empresas e tarefas
- Filtro por competencia e status
- Upload de anexo PDF por tarefa
- Feed de vencimentos e alertas
- Comentarios e confirmacao de leitura
- Configuracoes de servidor/email (admin)

## Arquitetura
Veja o detalhamento em `docs/ARCHITECTURE.md`.

Resumo:
- `web` consome endpoints REST do `server`
- `server` persiste dados em SQLite
- `desktop` (Tauri) empacota o `web` como app desktop

## API
Documentacao resumida em `docs/API.md`.

## Roadmap
Plano de evolucao em `docs/ROADMAP.md`.

## Demo visual
Capturas em `docs/screenshots/`:
- Login: `docs/screenshots/login.png`
- Home: `docs/screenshots/home.png`
- Empresas: `docs/screenshots/empresas.png`
- Tarefas: `docs/screenshots/tarefas.png`
- Relatorios: `docs/screenshots/relatorios.png`

## Como rodar local
### 1) Backend
```powershell
cd server
.\run_backend.ps1
```

### 2) Web
```powershell
cd web
npm install
npm run dev
```
Acesse: `http://127.0.0.1:5173`

### 3) Desktop (Tauri)
```powershell
cd desktop
npm install
npm run tauri:dev
```
Requer Rust + MSVC Build Tools + Windows SDK.

## CI
Workflow em `.github/workflows/ci.yml` com:
- build do frontend
- validacao sintatica do backend Python

## Changelog
Historico de versoes em `CHANGELOG.md`.

## Licenca
Este projeto esta sob licenca MIT (`LICENSE`).

## Autor
- GitHub: https://github.com/thiniciuz
- LinkedIn: (adicione seu link)
