# Arquitetura

## Componentes
- `web/`: interface React (Vite)
- `server/`: API FastAPI e persistencia SQLite
- `desktop/`: shell desktop Tauri para empacotar a interface web
- `client/`: versao desktop em PySide6 (legado/prototipo)

## Fluxo principal
1. Usuario autentica no frontend (`/auth/login`)
2. Frontend consulta empresas/tarefas via REST
3. Backend aplica regras de permissao por papel
4. Dados sao persistidos no SQLite
5. Upload de PDF dispara classificacao e notificacoes

## Decisoes tecnicas
- SQLite para simplicidade de deploy no MVP
- React + Vite para iteracao rapida no frontend
- FastAPI para API enxuta e tipada
- Tauri para empacotamento desktop com baixo overhead

## Trade-offs
- SQLite limita concorrencia em cenarios de alta escala
- Sem fila assíncrona dedicada para processamentos pesados
- Integracoes externas (email real, observabilidade completa) ainda em evolucao
