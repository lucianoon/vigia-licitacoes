from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

TENTATIVAS = 3


async def enviar(
    api_url: str,
    api_token: str,
    chat_id: str,
    mensagens: list[str],
) -> int:
    """Envia mensagens via WhatsApp (Evolution API).

    Retorna número de mensagens enviadas com sucesso.
    """
    if not api_url or not api_token or not chat_id:
        return 0

    url = f"{api_url.rstrip('/')}/message/sendText/{chat_id}"
    enviadas = 0

    async with httpx.AsyncClient(timeout=30.0) as client:
        for msg in mensagens:
            for tentativa in range(TENTATIVAS):
                try:
                    resposta = await client.post(
                        url,
                        headers={"apikey": api_token, "Content-Type": "application/json"},
                        json={"text": msg},
                    )
                    if resposta.status_code in (200, 201):
                        enviadas += 1
                        break
                    if resposta.status_code == 429:
                        logger.warning("WhatsApp rate limit (tentativa %d)", tentativa + 1)
                        continue
                    logger.warning(
                        "WhatsApp HTTP %d (tentativa %d): %s",
                        resposta.status_code, tentativa + 1,
                        resposta.text[:200],
                    )
                except httpx.TransportError as exc:
                    logger.warning("WhatsApp falhou (tentativa %d): %r", tentativa + 1, exc)
    return enviadas
