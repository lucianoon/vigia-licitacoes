# vigia-licitacoes

Monitor inteligente de licitações do **PNCP** (Portal Nacional de Contratações Públicas).
Você cadastra o que sua empresa vende em regras YAML; o Vigia varre as novas contratações,
filtra, resume cada edital compatível e avisa no **Telegram** antes do prazo fechar.

## Como funciona

```
PNCP (API aberta) → filtros globais → suas regras YAML
       → resumo por LLM (opcional) → alerta no Telegram
       → dedup em SQLite (nunca repete aviso)
```

## Instalação

```bash
git clone https://github.com/lucianoon/vigia-licitacoes
cd vigia-licitacoes
uv sync
```

## Configuração (5 minutos)

1. Crie um bot com [@BotFather](https://t.me/BotFather) no Telegram e copie o token
2. Descubra seu `chat_id` conversando com [@userinfobot](https://t.me/userinfobot)
3. Copie o exemplo e edite:

```bash
cp vigia.example.yaml vigia.yaml   # ajuste regras e chat_id
export TELEGRAM_TOKEN="123456:ABC..."
```

Opcional (resumo por IA): `export OPENAI_API_KEY=...` — aceita qualquer endpoint
compatível via `OPENAI_BASE_URL` e `VIGIA_MODELO`.

## Uso

```bash
# Ciclo de monitoramento (agende no cron a cada 8h)
uv run vigia run

# Teste as regras contra um texto de objeto, sem esperar o poll
uv run vigia test-regras "manutenção preventiva de ar-condicionado split"
```

Exemplo de alerta:

```
🎯 PE 138/2026 · R$ 60.000 · Pregão Eletrônico
🏛️ 7º BBM — Itajaí/SC
✅ Regra: Climatização (casou: "bombas de calor")
⏰ Propostas até 04/09 14:00 — faltam 9 dias

🤖 Manutenção preventiva/corretiva de sistemas de climatização
com fornecimento de peças, sob registro de preços.

🔗 https://pncp.gov.br/app/editais/...
```

Cron sugerido:

```
0 7,12,18 * * * cd ~/vigia && uv run vigia run >> vigia.log 2>&1
```

## Desenvolvimento

```bash
uv sync --dev
uv run pytest        # suíte completa (mocks)
uv run ruff check .
uv run mypy src
```

Logs detalhados: `VIGIA_LOG_LEVEL=DEBUG`.

## Roadmap

- [x] v0.1 — poll PNCP, regras YAML, Telegram, dedup SQLite, LLM opcional
- [ ] Digest semanal consolidado
- [ ] Urgência <48h destacada + lembrete de reenvio
- [ ] Multi-perfil (agências com vários clientes)
- [ ] Versão MCP server do PNCP

## Licença

MIT
