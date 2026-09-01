# Como contribuir

## Ambiente

```bash
uv sync --dev --locked        # mesmas versões do CI e da imagem Docker
cp vigia.example.yaml vigia.yaml
```

Tokens ficam em variáveis de ambiente (`TELEGRAM_TOKEN`, `OPENAI_API_KEY`,
`WHATSAPP_API_TOKEN`). Nunca faça commit de `vigia.yaml`, `.env` ou `vigia.db`;
todos já estão no `.gitignore`.

## Antes de abrir o PR

```bash
uv run ruff check .
uv run mypy src               # strict
uv run pytest -q
```

Os três comandos são exatamente os que o CI executa, em Python 3.12 e 3.14.
A suíte não faz chamada de rede: portais e canais são simulados com `respx`.
Um teste que precise de rede está errado.

## Dependências

Adicione ao `pyproject.toml` e rode `uv lock`. Faça commit do `uv.lock` junto:
o CI usa `uv sync --locked` e falha se o lock estiver desatualizado.

## Novos portais e canais

Portais implementam a interface em `src/vigia/portal.py` e entram em
`registry.py`. Canais seguem `notify.py`. Inclua testes com respostas
gravadas da API real, sem tokens.

## Registro de mudanças

Descreva a mudança em `CHANGELOG.md`, na seção **Não lançado**.
