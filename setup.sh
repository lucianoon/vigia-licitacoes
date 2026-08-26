#!/usr/bin/env bash
# ============================================================
# setup.sh — Setup completo do Vigia na máquina local
# ============================================================
# Uso:
#   chmod +x setup.sh
#   ./setup.sh
# ============================================================
set -euo pipefail

VIGIA_DIR="$(cd "$(dirname "$0")" && pwd)"
VIGIA_DB="$VIGIA_DIR/vigia.db"
VIGIA_LOG="$VIGIA_DIR/vigia.log"
CRON_TAG="# vigia-licitacoes"

echo "=== Vigia — Setup de Deploy Local ==="
echo

# 1. Verificar dependências
echo "[1/6] Verificando dependências..."
if ! command -v uv &>/dev/null; then
    echo "  ERRO: uv não encontrado. Instale: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi
if ! command -v python3 &>/dev/null; then
    echo " ERRO: python3 não encontrado."
    exit 1
fi
echo "  uv: $(uv --version)"
echo "  python: $(python3 --version)"

# 2. Instalar dependências do projeto
echo
echo "[2/6] Instalando dependências..."
cd "$VIGIA_DIR"
uv sync --quiet
echo "  Pronto."

# 3. Verificar TELEGRAM_TOKEN
echo
echo "[3/6] Verificando TELEGRAM_TOKEN..."
if [ -z "${TELEGRAM_TOKEN:-}" ]; then
    echo "  ⚠️  TELEGRAM_TOKEN não está definido."
    echo
    echo "  Para configurar:"
    echo "    1. Abra o Telegram e fale com @BotFather"
    echo "    2. Envie /newbot e siga as instruções"
    echo "    3. Copie o token (formato: 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz)"
    echo "    4. Adicione ao seu ~/.zshrc (ou ~/.bash_profile):"
    echo
    echo "       export TELEGRAM_TOKEN=\"SEU_TOKEN_AQUI\""
    echo
    echo "    5. Depois execute: source ~/.zshrc"
    echo
    echo "  Depois volte aqui e execute novamente: ./setup.sh"
    exit 1
else
    echo "  TELEGRAM_TOKEN definido (${TELEGRAM_TOKEN:0:8}...)"
fi

# 4. Verificar configuração
echo
echo "[4/6] Verificando vigia.yaml..."
if grep -q "COLOQUE_SEU_CHAT_ID_AQUI" "$VIGIA_DIR/vigia.yaml" 2>/dev/null; then
    echo "  ⚠️  vigia.yaml ainda tem chat_id de exemplo."
    echo
    echo "  Para descobrir seu chat_id:"
    echo "    1. Abra o Telegram e fale com @userinfobot"
    echo "    2. Copie o número (ex: 123456789)"
    echo "    3. Edite vigia.yaml e substitua 'COLOQUE_SEU_CHAT_ID_AQUI'"
    echo
    echo "  IMPORTANTE: Envie qualquer mensagem ('oi') pro seu bot novo"
    echo "  antes de rodar — o Telegram só permite envio após primeiro contato."
    echo
    read -p "  Pressione Enter depois de configurar o chat_id (ou Ctrl+C para sair)... "
else
    echo "  chat_id configurado."
fi

# 5. Testar conexão
echo
echo "[5/6] Testando conexão com o PNCP..."
if uv run vigia test-regras "manutenção preventiva de ar-condicionado" --config "$VIGIA_DIR/vigia.yaml" 2>/dev/null | grep -q "✅"; then
    echo "  ✅ Regras funcionando."
else
    echo "  ⚠️  Teste de regras falhou (pode ser normal se o PNCP estiver fora)."
fi

# 6. Configurar cron
echo
echo "[6/6] Configurando cron..."

# Gerar entrada do cron
CRON_CMD="0 7,12,18 * * * cd $VIGIA_DIR && TELEGRAM_TOKEN=\"\$TELEGRAM_TOKEN\" uv run vigia run >> $VIGIA_LOG 2>&1"

# Verificar se já existe
if crontab -l 2>/dev/null | grep -qF "$CRON_TAG"; then
    echo "  Cron já configurado. Atualizando..."
    # Remover entrada antiga
    crontab -l 2>/dev/null | grep -vF "$CRON_TAG" | crontab - 2>/dev/null || true
fi

# Adicionar nova entrada
(crontab -l 2>/dev/null; echo "$CRON_CMD  $CRON_TAG") | crontab -
echo "  ✅ Cron configurado para rodar às 7h, 12h e 18h."

# Resumo
echo
echo "============================================"
echo "  ✅ Setup completo!"
echo "============================================"
echo
echo "  Próximos passos:"
echo "    1. Configure o TELEGRAM_TOKEN (se ainda não fez)"
echo "    2. Configure o chat_id no vigia.yaml"
echo "    3. Envie 'oi' pro bot no Telegram"
echo "    4. Teste: uv run vigia run --dry-run"
echo "    5. Rodar de verdade: uv run vigia run"
echo
echo "  Cron rodando às: 07:00, 12:00, 18:00"
echo "  Log: $VIGIA_LOG"
echo "  Config: $VIGIA_DIR/vigia.yaml"
echo
echo "  Comandos úteis:"
echo "    uv run vigia run                    # ciclo único"
echo "    uv run vigia run --dry-run          # sem enviar"
echo "    uv run vigia digest                 # resumo semanal"
echo "    uv run vigia digest --enviar        # digest no Telegram"
echo "    uv run vigia test-regras \"texto\"    # testar regras"
echo
echo "  Para remover o cron:"
echo "    crontab -l | grep -v '$CRON_TAG' | crontab -"
