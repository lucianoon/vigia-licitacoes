# vigia-licitacoes

*[English version](README.en.md)*

Monitor inteligente de licitações do **PNCP** (Portal Nacional de Contratações Públicas).
Funciona para **qualquer segmento**: climatização, saúde, TI, petroquímica, escritório,
construção civil, alimentação, e qualquer outro nicho que venda para o governo.

Você cadastra o que sua empresa vende em regras YAML; o Vigia varre as novas contratações,
filtra, resume cada edital compatível e avisa no **Telegram** antes do prazo fechar.

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
| Climatização / HVAC | ar-condicionado, bombas de calor, chiller, refrigeracao |
| Saúde / Farmacêutico | medicamento, insumo hospitalar, equipamento médico |
| TI / Software | servidor, cloud, storage, desenvolvimento, licença |
| Petroquímica / Energia | combustível, lubrificante, tubulacao, válvula |
| Material de escritório | papelaria, mobiliário, computador, impressora |
| Construção civil | obra, reforma, pavimentacao, elétrica, hidráulica |
| Alimentação | gênero alimentício, merenda, alimentação escolar |
| Serviços | limpeza, vigilância, manutenção, consultoria |

Basta criar regras YAML com as palavras-chave do seu segmento.

## Instalação

```bash
git clone https://github.com/lucianoon/vigia-licitacoes
cd vigia-licitacoes
uv sync
```

## Configuração rápida (5 minutos)

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

## Deploy local (cron automático)

```bash
./setup.sh
```

O script configura cron para rodar às 7h, 12h e 18h.

## Uso

```bash
# Ciclo de monitoramento
uv run vigia run

# Modo dry-run (mostra alertas sem enviar)
uv run vigia run --dry-run

# Rodar apenas um perfil especifico
uv run vigia run --perfil "Climatizacao SP"

# Restringir a consulta e/ou o canal
uv run vigia run --portal pncp --canal telegram

# Digest semanal (resumo consolidado)
uv run vigia digest
uv run vigia digest --enviar  # envia no Telegram

# Testar regras contra um texto
uv run vigia test-regras "manutencao preventiva de ar-condicionado"

# Dashboard HTML (abre no navegador)
uv run vigia dashboard
```

## Multi-perfil

O Vigia suporta múltiplos perfis num só arquivo. Útil para:
- Agências que atendem várias empresas
- Empresas com áreas de compra diferentes
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
- Histórico de alertas por perfil
- Top licitações por valor
- Métricas (alertas enviados, taxa por regra)
- Gráfico de atividade semanal

## Regras YAML

Cada regra tem:

```yaml
- nome: "Nome da Regra"
  qualquer: ["termo1", "termo2"]    # casa se QUALQUER um aparecer
  excluir: ["termo_errado"]         # veto se aparecer
  destaque: ["termo_bom"]           # bonus de score
```

- `qualquer`: lista de termos. O item casa se QUALQUER termo aparecer no objeto
- `excluir`: veto. Se QUALQUER termo aparecer, o match é descartado
- `destaque`: bônus. Aumenta o score do match (mais urgência)

Exemplo: "manutenção preventiva de ar-condicionado" casa com:
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

## Docker

O container executa um ciclo e termina. Para rodar manualmente:

```bash
docker compose run --rm vigia run
```

Para agendar, execute esse comando pelo cron ou por outro scheduler. O histórico e os
backups ficam em `./data`. O Compose não usa política de reinício automático para evitar
que um processo de ciclo único rode em loop e envie alertas repetidamente.

Variáveis úteis:

- `VIGIA_DB_PATH`: caminho do SQLite (padrão: `vigia.db`)
- `VIGIA_BACKUP_DIR`: diretório de backups (padrão: `./backups`)
- `VIGIA_BACKUP_KEEP`: quantidade máxima de backups preservados (padrão: 30)

## Roadmap

- [x] v0.1 — poll PNCP, regras YAML, Telegram, dedup SQLite, LLM opcional
- [x] Multi-perfil (vários perfis num só config, herança de filtros)
- [x] Urgência +48h + lembretes
- [x] Digest semanal consolidado
- [x] Cache local PNCP (evita requests duplicados)
- [x] Dashboard HTML (histórico + metricas)
- [x] Alertas por WhatsApp via Evolution API
- [ ] Multi-portal (Petronect, ComprasNet, BNB)
- [ ] API REST para integração
- [ ] Modo SaaS (multi-tenant com auth)

## Licença

MIT
