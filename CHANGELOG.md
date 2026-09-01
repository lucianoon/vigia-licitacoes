# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)
e versionamento semântico.

## [Não lançado]

### Adicionado

- `SECURITY.md`, `CONTRIBUTING.md` e este CHANGELOG.
- Dependabot para GitHub Actions e dependências Python (mensal, minor/patch agrupados).
- Job de CI que constrói a imagem Docker e executa o CLI instalado pelo lockfile.
- README em inglês (`README.en.md`); README em português com acentuação.
- Topics no repositório e CodeQL habilitado.

### Alterado

- CI sincroniza com `uv sync --locked`, falhando se o `uv.lock` estiver desatualizado.

## [0.1.0] — 2026-08-26

Primeira versão. Todo o desenvolvimento inicial aconteceu em um único dia.

### Adicionado

- Monitor do PNCP: coleta de contratações, filtros globais e regras YAML com
  `qualquer`, `excluir` e `destaque`.
- Alertas no Telegram; resumo opcional de cada edital por LLM.
- Dedup em SQLite para nunca repetir um aviso.
- Modo `--dry-run` no `vigia run`.
- Multi-perfil: vários perfis num só arquivo, com herança de filtros.
- Urgência: ordenação por prazo e lembretes para itens críticos (+48h).
- Digest semanal consolidado por perfil, com envio opcional.
- `setup.sh`: deploy local com cron automático (7h, 12h e 18h).
- Cache local das consultas ao PNCP, dashboard HTML com histórico e métricas,
  mensagens de erro claras, suporte a qualquer nicho.
- Multi-portal (arquitetura em `portal.py` e `registry.py`), alertas por
  WhatsApp via Evolution API, execução assíncrona e exportação CSV/XLSX.
- Retry exponencial nas chamadas HTTP, health check dos portais, backup do
  SQLite e logging em JSON.
- Suíte de testes com `respx`, Dockerfile e `docker-compose.yml`.

### Removido

- Portal Petronect: não tem API pública.
