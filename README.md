# vigia-licitacoes

Monitor inteligente de licitacoes do **PNCP** (Portal Nacional de Contratacoes Publicas).
Voce cadastra o que sua empresa vende em regras YAML; o Vigia varre as novas contratacoes,
filtra, resume cada edital compativel e avisa no **Telegram** antes do prazo fechar.

## Como funciona

```
PNCP (API aberta) -> filtros globais -> suas regras YAML
       -> resumo por LLM (opcional) -> alerta no Telegram
       -> dedup em SQLite (nunca repete aviso)
```

## Instalacao

```bash
git clone https://github.com/lucianoon/vigia-licitacoes
cd vigia-licitacoes
uv sync
```

## Configuracao (5 minutos)

1. Crie um bot com [@BotFather](https://t.me/BotFather) no Telegram e copie o token
2. Descubra seu `chat_id` conversando com [@userinfobot](https://t.me/userinfobot)
3. Copie o exemplo e edite:

```bash
cp vigia.example.yaml vigia.yaml   # ajuste regras e chat_id
export TELEGRAM_TOKEN="123456:ABC..."
```

Opcional (resumo por IA): `export OPENAI_API_KEY=...` -- aceita qualquer endpoint
compativel via `OPENAI_BASE_URL` e `VIGIA_MODELO`.

## Uso

```bash
# Ciclo de monitoramento (agende no cron a cada 8h)
uv run vigia run

# Teste as regras contra um texto de objeto, sem esperar o poll
uv run vigia test-regras "manutencao preventiva de ar-condicionado split"

# Modo dry-run (mostra alertas sem enviar)
uv run vigia run --dry-run

# Rodar apenas um perfil especifico
uv run vigia run --perfil "Climatizacao SP"
```

Exemplo de alerta:

```
🎯 PE 138/2026 · R$ 60.000 · Pregao Eletronico
🏛️ 7º BBM — Itajai/SC
✅ Regra: Climatizacao (casou: "bombas de calor")
⏰ Propostas ate 04/09 14:00 — faltam 9 dias

🤖 Manutencao preventiva/corretiva de sistemas de climatizacao
com fornecimento de pecas, sob registro de precos.

🔗 https://pncp.gov.br/app/editais/...
```

## Multi-perfil

O Vigia suporta multiplos perfis num so arquivo de configuracao. Cada perfil tem
suas regras, filtros e chat_id do Telegram. Util para agencias que atendem varias
empresas, ou para uma empresa com areas de compra diferentes.

```yaml
perfis:
  - nome: "Climatizacao SP"
    telegram:
      chat_id: "111"
    filtros_globais:
      ufs: ["SP"]
      valor_minimo: 50000
    regras:
      - nome: "Climatizacao"
        qualquer: ["climatizacao", "ar-condicionado"]
        destaque: ["preventiva"]

  - nome: "Medicamentos BA"
    telegram:
      chat_id: "222"
    regras:
      - nome: "Medicamentos"
        qualquer: ["medicamento"]
```

**Heranca**: filtros do root sao herdados por todos os perfis. Cada perfil pode
sobrescrever apenas os campos que quiser (merge profundo).

**Backward compat**: config antigo (root `telegram` + `regras`) continua funcionando
-- vira automaticamente "Perfil Padrao".

Cron sugerido:

```
0 7,12,18 * * * cd ~/vigia && uv run vigia run >> vigia.log 2>&1
```

## Desenvolvimento

```bash
uv sync --dev
uv run pytest        # suite completa (30 testes)
uv run ruff check .
uv run mypy src
```

Logs detalhados: `VIGIA_LOG_LEVEL=DEBUG`.

## Roadmap

- [x] v0.1 -- poll PNCP, regras YAML, Telegram, dedup SQLite, LLM opcional
- [x] Multi-perfil (varios perfis num so config, heranca de filtros)
- [ ] Digest semanal consolidado
- [ ] Urgencia <48h destacada + lembrete de reenvio
- [ ] Versao MCP server do PNCP

## Licenca

MIT
