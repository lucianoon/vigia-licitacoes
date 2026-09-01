# vigia-licitacoes

*[Versão em português](README.md)*

Smart monitor for public tenders published on **PNCP** (Brazil's National Public Procurement Portal).
Works for **any segment**: HVAC, healthcare, IT, petrochemicals, office supplies, construction,
food services, and any other niche that sells to the Brazilian government.

You describe what your company sells as YAML rules; Vigia scans new procurement notices,
filters them, summarizes every matching tender and alerts you on **Telegram** before the deadline closes.

## How it works

```
PNCP (open API) -> local cache -> filters -> your YAML rules
       -> LLM summary (optional) -> Telegram alert
       -> SQLite dedup (never repeats an alert)
       -> HTML dashboard (history + metrics)
```

## Any niche is supported

| Segment | Example rules |
|---|---|
| HVAC | air conditioning, heat pumps, chillers, refrigeration |
| Healthcare / Pharma | medicines, hospital supplies, medical equipment |
| IT / Software | servers, cloud, storage, development, licenses |
| Petrochemicals / Energy | fuel, lubricants, piping, valves |
| Office supplies | stationery, furniture, computers, printers |
| Construction | works, renovation, paving, electrical, plumbing |
| Food services | foodstuffs, school meals |
| Services | cleaning, security, maintenance, consulting |

Write YAML rules with the keywords of your segment (in Portuguese, since that is the language
of the notices). Matching is accent-insensitive.

## Installation

```bash
git clone https://github.com/lucianoon/vigia-licitacoes
cd vigia-licitacoes
uv sync
```

## Quick setup (5 minutes)

1. Create a bot with [@BotFather](https://t.me/BotFather) on Telegram and copy the token
2. Find your `chat_id` by messaging [@userinfobot](https://t.me/userinfobot)
3. Copy the example config and edit it:

```bash
cp vigia.example.yaml vigia.yaml
vim vigia.yaml  # adjust rules, chat_id and segment
export TELEGRAM_TOKEN="123456:ABC..."
```

4. Send any message ("hi") to your new bot on Telegram
5. Test it:

```bash
uv run vigia run --dry-run
```

Optional (AI summaries): `export OPENAI_API_KEY=...`

## Local deploy (automatic cron)

```bash
./setup.sh
```

The script installs a cron schedule that runs at 7 am, 12 pm and 6 pm.

## Usage

```bash
# Monitoring cycle
uv run vigia run

# Dry run (prints alerts without sending them)
uv run vigia run --dry-run

# Run a single profile
uv run vigia run --perfil "Climatizacao SP"

# Restrict the portal and/or the channel
uv run vigia run --portal pncp --canal telegram

# Weekly digest (consolidated summary)
uv run vigia digest
uv run vigia digest --enviar  # sends it on Telegram

# Test your rules against a text
uv run vigia test-regras "manutencao preventiva de ar-condicionado"

# HTML dashboard (opens in the browser)
uv run vigia dashboard
```

## Multiple profiles

Vigia supports several profiles in a single file. Useful for:
- Agencies serving several companies
- Companies with distinct purchasing areas
- One team monitoring different niches

```yaml
perfis:
  - nome: "Climatizacao SP"
    telegram: { chat_id: "111" }
    filtros_globais: { ufs: ["SP"], valor_minimo: 50000 }
    regras:
      - nome: "Climatizacao"
        qualquer: ["climatizacao", "ar-condicionado"]

  - nome: "Medicamentos BA"
    telegram: { chat_id: "222" }
    regras:
      - nome: "Medicamentos"
        qualquer: ["medicamento", "farmaceutico"]

  - nome: "TI Generico"
    telegram: { chat_id: "333" }
    regras:
      - nome: "Infraestrutura"
        qualquer: ["servidor", "data center", "cloud"]
```

## Dashboard

```bash
uv run vigia dashboard
# Opens dashboard.html in the browser
```

It shows:
- Alert history per profile
- Top tenders by value
- Metrics (alerts sent, hit rate per rule)
- Weekly activity chart

## YAML rules

Each rule has:

```yaml
- nome: "Rule name"
  qualquer: ["term1", "term2"]      # matches if ANY term appears
  excluir: ["wrong_term"]           # veto if it appears
  destaque: ["good_term"]           # score bonus
```

- `qualquer`: list of terms. The item matches if ANY term appears in the notice object
- `excluir`: veto. If ANY term appears, the match is discarded
- `destaque`: bonus. Raises the match score (higher urgency)

Example: "manutencao preventiva de ar-condicionado" (preventive air-conditioning maintenance) matches:
- `qualquer: ["ar-condicionado"]` ✅
- `destaque: ["preventiva"]` ✅ (higher score)
- `excluir: ["locacao"]` ❌ (veto)

## Development

```bash
uv sync --dev
uv run pytest        # full suite (40+ tests)
uv run ruff check .
uv run mypy src
```

Verbose logs: `VIGIA_LOG_LEVEL=DEBUG`.

## Docker

The container runs one cycle and exits. To run it manually:

```bash
docker compose run --rm vigia run
```

Schedule that command with cron or another scheduler. History and backups live in `./data`.
The Compose file deliberately sets no restart policy, so a single-cycle process never loops
and re-sends alerts.

Useful variables:

- `VIGIA_DB_PATH`: SQLite path (default: `vigia.db`)
- `VIGIA_BACKUP_DIR`: backup directory (default: `./backups`)
- `VIGIA_BACKUP_KEEP`: maximum number of backups kept (default: 30)

## Roadmap

- [x] v0.1 — PNCP polling, YAML rules, Telegram, SQLite dedup, optional LLM
- [x] Multiple profiles (several profiles in one config, filter inheritance)
- [x] 48-hour urgency window + reminders
- [x] Consolidated weekly digest
- [x] Local PNCP cache (avoids duplicate requests)
- [x] HTML dashboard (history + metrics)
- [x] WhatsApp alerts via Evolution API
- [ ] Multi-portal (Petronect, ComprasNet, BNB)
- [ ] REST API for integrations
- [ ] SaaS mode (multi-tenant with auth)

## License

MIT
