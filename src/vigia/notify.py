import logging
from datetime import datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)

TELEGRAM_URL = "https://api.telegram.org"


class TelegramError(Exception):
    pass


async def enviar(token: str, chat_id: str, mensagens: list[str]) -> int:
    """Envia mensagens no Telegram; retorna quantas foram entregues."""
    if not mensagens:
        return 0
    enviadas = 0
    async with httpx.AsyncClient(timeout=15.0) as client:
        for mensagem in mensagens:
            resposta = await client.post(
                f"{TELEGRAM_URL}/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": mensagem},
            )
            dados = _json_ou_erro(resposta)
            if not dados.get("ok"):
                raise TelegramError(f"Telegram rejeitou a mensagem: {dados}")
            enviadas += 1
    return enviadas


def _json_ou_erro(resposta: httpx.Response) -> dict[str, Any]:
    try:
        dados: dict[str, Any] = resposta.json()
    except ValueError as exc:
        raise TelegramError(
            f"Resposta não-JSON do Telegram (HTTP {resposta.status_code})"
        ) from exc
    return dados


def formatar_alerta(item: dict[str, Any], resultado: Any, resumo_llm: str | None) -> str:
    unidade = item.get("unidadeOrgao") or {}
    entidade = item.get("orgaoEntidade") or {}

    sigla = str(item.get("numeroCompra") or "?")
    ano = str(item.get("anoCompra") or "?")
    valor = item.get("valorTotalEstimado")
    if isinstance(valor, int | float):
        valor_txt = f"R$ {float(valor):,.0f}".replace(",", ".")
    else:
        valor_txt = "valor não informado"

    modalidade_nome = item.get("modalidadeNome") or MODALIDADE_PADRAO(item)
    orgao = entidade.get("razaoSocial") or unidade.get("nomeUnidade") or "órgão não informado"
    municipio = unidade.get("municipio") or "?"
    uf = unidade.get("uf") or "?"

    prazo_txt = _formatar_prazo(item.get("dataEncerramentoProposta"))

    termos = ", ".join(f"“{t}”" for t in resultado.termos_casados)
    linhas = [
        f"🎯 {sigla}/{ano} · {valor_txt} · {modalidade_nome}",
        f"🏛️ {orgao} — {municipio}/{uf}",
        f"✅ Regra: {resultado.regra} (casou: {termos})",
        f"⏰ {prazo_txt}",
    ]
    if resultado.destaques:
        linhas.insert(3, f"⭐ Destaques: {', '.join(resultado.destaques)}")

    resumo = resumo_llm or _trecho_objeto(item)
    linhas.append("")
    linhas.append(resumo)

    controle = str(item.get("numeroControlePNCP") or "")
    if controle:
        linhas.append("")
        linhas.append(f"🔗 https://pncp.gov.br/app/editais/{controle}")
    return "\n".join(linhas)


MODALIDADES_CONHECIDAS = {
    6: "Pregão Eletrônico",
    4: "Concorrência Eletrônica",
    1: "Leilão Eletrônico",
}


def MODALIDADE_PADRAO(item: dict[str, Any]) -> str:  # noqa: N802
    codigo = item.get("modalidadeId")
    chave = int(codigo) if isinstance(codigo, int) else -1
    return MODALIDADES_CONHECIDAS.get(chave, f"Modalidade {codigo}")


def _formatar_prazo(data_encerramento: Any) -> str:
    if not data_encerramento:
        return "Prazo de propostas ainda não informado"
    try:
        momento = datetime.fromisoformat(str(data_encerramento))
    except ValueError:
        return f"Prazo: {data_encerramento}"
    restantes = (momento - datetime.now()).days
    quando = momento.strftime("%d/%m %H:%M")
    if restantes < 0:
        return f"Encerrado em {quando}"
    if restantes <= 2:
        return f"⚠️ Propostas até {quando} — URGENTE ({restantes} dia(s))"
    return f"Propostas até {quando} — faltam {restantes} dias"


def _trecho_objeto(item: dict[str, Any], limite: int = 280) -> str:
    objeto = str(item.get("objetoCompra") or "").strip()
    if len(objeto) > limite:
        return f"{objeto[:limite]}..."
    return objeto
