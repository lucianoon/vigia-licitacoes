# Política de segurança

## Versões suportadas

O branch `main` recebe correções de segurança. Commits antigos não recebem
backports garantidos.

## Reportar uma vulnerabilidade

Não abra uma issue pública. Use **Security → Report a vulnerability** neste
repositório para enviar o relato de forma privada.

Inclua o commit afetado, o impacto, os passos mínimos para reprodução e, se
possível, uma mitigação. O objetivo é confirmar o recebimento em até 3 dias
úteis e publicar uma avaliação inicial em até 7 dias úteis.

## Escopo sensível

O Vigia lê editais públicos, guarda histórico em SQLite e envia alertas por
Telegram e WhatsApp. São especialmente relevantes relatos sobre:

- vazamento de `TELEGRAM_TOKEN`, `OPENAI_API_KEY` ou `WHATSAPP_API_TOKEN` em
  logs, mensagens de erro, dashboard ou exportações;
- injeção de conteúdo vindo do texto dos editais que manipule o resumo por LLM
  ou o conteúdo enviado aos canais;
- regras YAML ou configurações que levem a consumo excessivo da API do PNCP;
- gravação fora dos diretórios esperados via `VIGIA_DB_PATH` ou
  `VIGIA_BACKUP_DIR`.

Não inclua tokens reais nem dados de terceiros no relato.
