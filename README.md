# vigia-licitacoes

Monitor inteligente de licitacoes do **PNCP** (Portal Nacional de Contratacoes Publicas).
Funciona para **qualquer segmento**: climatizacao, saude, TI, petroquimica, escritorio,
construcao civil, alimentacao, e qualquer outro nicho que venda para o governo.

Voce cadastra o que sua empresa vende em regras YAML; o Vigia varre as novas contratacoes,
filtra, resume cada edital compativel e avisa no **Telegram** antes do prazo fechar.

## Como funciona

```
PNCP (API aberta) -> cache local -> filtros -> suas regras YAML
       -> resumo por LLM (opcional) -> alerta no Telegram
       -> dedup em SQLite (nunca repete aviso)
       -> dashboard HTML (historico + metricas)
```

## Suporta qualquer nicho

| Segmento | Exemplos de regras |
|---|---|
| Climatizacao / HVAC | ar-condicionado, bombas de calor, chiller, refrigeracao |
| Saude / Farmaceutico | medicamento, insumo hospitalar, equipamento medico |
| TI / Software | servidor, cloud, storage, desenvolvimento, licenca |
| Petroquimica / Energia | combustivel, lubrificante, tubulacao, valvula |
| Material de escritorio | papelaria, mobiliario, computador, impressora |
| Construcao civil | obra, reforma, pavimentacao, eletrica, hidraulica |
| Alimentacao | genero alimenticio, merenda, alimentacao escolar |
| Servicos | limpeza, vigilancia, manutencao, consultoria |

Basta criar regras YAML com as palavras-chave do seu segmento.

## Instalacao

```bash
git clone https://github.com/lucianoon/vigia-licitacoes
cd vigia-licitacoes
uv sync
```

## Configuracao rapida (5 minutos)

1. Crie um bot com [@BotFather](https://t.me/BotFather) no Telegram e copie o token
2. Descubra seu `chat_id` conversando com [@userinfobot](https://t.me/userinfobot)
3. Copie o exemplo e edite:

```bash
cp vigia.example.yaml vigia.yaml
vim vigia.yaml  # ajuste regras, chat_id e segmento
export TELEGRAM_TOKEN="123456:ABC..."
```

4. Envie qualquer mensagem ("oi") pro seu bot novo no Telegram
5. Teste:

```bash
uv run vigia run --dry-run
```

Opcional (resumo por IA): `export OPENAI_API_KEY=...`

## Deploy local (cron automatico)

```bash
./setup.sh
```

O script configura cron para rodar as 7h, 12h e 18h.

## Uso

```bash
# Ciclo de monitoramento
uv run vigia run

# Modo dry-run (mostra alertas sem enviar)
uv run vigia run --dry-run

# Rodar apenas um perfil especifico
uv run vigia run --perfil "Climatizacao SP"

# Digest semanal (resumo consolidado)
uv run vigia digest
uv run vigia digest --enviar  # envia no Telegram

# Testar regras contra um texto
uv run vigia test-regras "manutencao preventiva de ar-condicionado"

# Dashboard HTML (abre no navegador)
uv run vigia dashboard
```

## Multi-perfil

O Vigia suporta multiplos perfis num so arquivo. Util para:
- Agencias que atendem varias empresas
- Empresas com areas de compra diferentes
- Um mesmo time monitorando nichos distintos

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
# Abre dashboard.html no navegador
```

Mostra:
- Historico de alertas por perfil
- Top licitacoes por valor
- Metricas (alertas enviados, taxa por regra)
- Grafico de atividade semanal

## Regras YAML

Cada regra tem:

```yaml
- nome: "Nome da Regra"
  qualquer: ["termo1", "termo2"]    # casa se QUALQUER um aparecer
  excluir: ["termo_errado"]         # veto se aparecer
  destaque: ["termo_bom"]           # bonus de score
```

- `qualquer`: lista de termos. O item casa se QUALQUER termo aparecer no objeto
- `excluir`: veto. Se QUALQUER termo aparecer, o match e descartado
- `destaque`: bonus. Aumenta o score do match (mais urgencia)

Exemplo: "manutencao preventiva de ar-condicionado" casa com:
- `qualquer: ["ar-condicionado"]` ✅
- `destaque: ["preventiva"]` ✅ (score maior)
- `excluir: ["locacao"]` ❌ (veto)

## Desenvolvimento

```bash
uv sync --dev
uv run pytest        # suite completa (36+ testes)
uv run ruff check .
uv run mypy src
```

Logs detalhados: `VIGIA_LOG_LEVEL=DEBUG`.

## Roadmap

- [x] v0.1 — poll PNCP, regras YAML, Telegram, dedup SQLite, LLM opcional
- [x] Multi-perfil (varios perfis num so config, heranca de filtros)
- [x] Urgencia +48h + lembretes
- [x] Digest semanal consolidado
- [x] Cache local PNCP (evita requests duplicados)
- [x] Dashboard HTML (historico + metricas)
- [ ] Alertas por WhatsApp (WhatsApp Business API)
- [ ] Multi-portal (Petronect, ComprasNet, BNB)
- [ ] API REST para integracao
- [ ] Modo SaaS (multi-tenant com auth)

## Licenca

MIT
