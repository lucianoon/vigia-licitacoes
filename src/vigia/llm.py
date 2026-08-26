import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

PROMPT = (
    "Você é um analista de licitações. Resuma a contratação abaixo em no máximo "
    "3 linhas em português, dizendo O QUE está sendo comprado, PARA QUEM e um "
    "ponto de atenção (ex.: SRP, prazo curto, escopo amplo). Seja direto, sem saudação.\n\n"
)


async def resumir(item: dict[str, Any]) -> str | None:
    """Resume o edital via LLM compatível com OpenAI. Nunca levanta exceção."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    modelo = os.environ.get("VIGIA_MODELO", "gpt-4o-mini")
    objeto = str(item.get("objetoCompra") or "")[:1500]
    orgao = str(((item.get("orgaoEntidade") or {}).get("razaoSocial")) or "")
    pergunta = f"{PROMPT}Órgão: {orgao}\nObjeto: {objeto}"

    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            resposta = await client.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": modelo,
                    "messages": [{"role": "user", "content": pergunta}],
                    "max_tokens": 200,
                    "temperature": 0.2,
                },
            )
            resposta.raise_for_status()
            conteudo = resposta.json()["choices"][0]["message"]["content"]
            texto = str(conteudo).strip()
            return texto or None
    except Exception as exc:
        logger.warning("Resumo LLM falhou (alerta segue sem enriquecimento): %r", exc)
        return None
