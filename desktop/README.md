Desktop Web (Tauri)
===================

Este diretório contém o app desktop Tauri que carrega o frontend em `../web`.

Pré-requisitos (Windows)
1. Node.js + npm.
2. Rust (via rustup): https://rustup.rs/
3. Visual Studio Build Tools com MSVC + Windows SDK:
   https://aka.ms/vs/17/release/vs_BuildTools.exe

Rodar em desenvolvimento
1. Backend (terminal 1):
   - `cd ../server`
   - `.\run_backend.ps1`
2. Desktop (terminal 2):
   - `cd desktop`
   - `npm install`
   - `npm run tauri:dev`

Observações
- O comando `tauri:dev` já sobe o frontend (`../web`) automaticamente.
- O backend precisa estar rodando separadamente em `http://127.0.0.1:8000`.

Build do app desktop
1. `cd desktop`
2. `npm install`
3. `npm run tauri:build`
