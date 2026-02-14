# API (Resumo)

Base URL local: `http://127.0.0.1:8000`

## Health
- `GET /health`

## Autenticacao
- `POST /auth/login`

## Usuarios
- `GET /users`
- `POST /users`
- `PATCH /users/{user_id}/role`

## Empresas
- `GET /companies`
- `POST /companies`
- `PATCH /companies/{company_id}`
- `PATCH /companies/{company_id}/responsavel`

## Tarefas
- `GET /tasks`
- `GET /tasks/upcoming`
- `POST /tasks`
- `PATCH /tasks/{task_id}`
- `PATCH /tasks/{task_id}/status`
- `POST /tasks/{task_id}/pdf`
- `GET /tasks/{task_id}/pdf`
- `GET /tasks/{task_id}/logs`
- `GET /tasks/{task_id}/comments`
- `POST /tasks/{task_id}/comments`
- `POST /tasks/{task_id}/comments/{comment_id}/ack`

## Notificacoes
- `GET /notifications`
- `PATCH /notifications/{notification_id}/read`

## Configuracoes (admin)
- `GET /settings/server`
- `PATCH /settings/server`
- `GET /settings/email`
- `PATCH /settings/email`

## Manutencao
- `POST /maintenance/sync-monthly`

Para detalhes de payloads, consulte os schemas em `server/app/schemas.py`.
