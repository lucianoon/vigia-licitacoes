from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from typing import Any

import httpx

from vigia.cache import CachePncp
from vigia.portal import Portal, Publicacao

logger = logging.getLogger(__name__)

PNCP_URL = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"
TAMANHO_PAGINA = 50
MAX_PAGINAS = 200
PAUSA_ENTRE_PAGINAS = 3.0
ESPERA_RATE_LIMIT = 45.0
TENTATIVAS_POR_PAGINA = 4

MODALIDADES_CONHECIDAS = {
    1: "Leilao Eletronico",
    4: "Concorrencia Eletronica",
    6: "Pregao Eletronico",
}


class PncpError(Exception):
    pass


async def _obter_pagina(
    client: httpx.AsyncClient,
    data_inicial: date,
    data_final: date,
    codigo_modalidade: int,
    pagina: int,
    cache: CachePncp | None = None,
) -> dict[str, Any]:
    di = data_inicial.strftime("%Y%m%d")
    df = data_final.strftime("%Y%m%d")

    if cache:
        dados_cache = cache.buscar(di, df, [codigo_modalidade], pagina, TAMANHO_PAGINA)
        if dados_cache is not None:
            logger.debug("Cache hit: modalidade %d, página %d", codigo_modalidade, pagina)
            return dados_cache

    params = {
        "dataInicial": di,
        "dataFinal": df,
        "codigoModalidadeContratacao": str(codigo_modalidade),
        "pagina": str(pagina),
        "tamanhoPagina": str(TAMANHO_PAGINA),
    }
    ultimo_erro: Exception | None = None
    for tentativa in range(TENTATIVAS_POR_PAGINA):
        try:
            resposta = await client.get(PNCP_URL, params=params)
            if resposta.status_code == 429:
                logger.warning(
                    "Rate limit do PNCP (modalidade %d, página %d); "
                    "aguardando %.0fs...",
                    codigo_modalidade,
                    pagina,
                    ESPERA_RATE_LIMIT,
                )
                await asyncio.sleep(ESPERA_RATE_LIMIT)
                ultimo_erro = PncpError("HTTP 429: limite de requisições do PNCP")
                continue
            if resposta.status_code in (502, 503, 504):
                logger.warning(
                    "PNCP indisponível (HTTP %d, modalidade %d, página %d); "
                    "tentativa %d/%d",
                    resposta.status_code,
                    codigo_modalidade,
                    pagina,
                    tentativa + 1,
                    TENTATIVAS_POR_PAGINA,
                )
                ultimo_erro = PncpError(
                    f"HTTP {resposta.status_code} do PNCP"
                )
                if tentativa < TENTATIVAS_POR_PAGINA - 1:
                    await asyncio.sleep(5.0 * (tentativa + 1))
                continue
            if resposta.status_code >= 400:
                raise PncpError(
                    f"HTTP {resposta.status_code} na consulta do PNCP "
                    f"(modalidade {codigo_modalidade}, página {pagina}): {resposta.text[:200]}"
                )
            try:
                dados: dict[str, Any] = resposta.json()
            except ValueError as exc:
                raise PncpError(f"Resposta não-JSON do PNCP: {exc}") from exc
            if cache:
                cache.salvar(di, df, [codigo_modalidade], pagina, TAMANHO_PAGINA, dados)
            return dados
        except httpx.TransportError as exc:
            ultimo_erro = exc
            logger.warning(
                "Tentativa %d falhou (modalidade %d, página %d): %r",
                tentativa + 1,
                codigo_modalidade,
                pagina,
                exc,
            )
            if tentativa < TENTATIVAS_POR_PAGINA - 1:
                await asyncio.sleep(2.0 * (tentativa + 1))
    raise PncpError(
        f"PNCP indisponível após {TENTATIVAS_POR_PAGINA} tentativas "
        f"(modalidade {codigo_modalidade}, página {pagina}): {ultimo_erro}"
    ) from ultimo_erro


async def _buscar_modalidade(
    client: httpx.AsyncClient,
    data_inicial: date,
    data_final: date,
    codigo_modalidade: int,
    cache: CachePncp | None = None,
) -> list[dict[str, Any]]:
    itens: list[dict[str, Any]] = []
    pagina = 1
    while pagina <= MAX_PAGINAS:
        dados = await _obter_pagina(
            client, data_inicial, data_final, codigo_modalidade, pagina, cache
        )

        lote = dados.get("data") or []
        itens.extend(item for item in lote if isinstance(item, dict))

        paginas_restantes = int(dados.get("paginasRestantes") or 0)
        if paginas_restantes <= 0:
            break
        pagina += 1
        await asyncio.sleep(PAUSA_ENTRE_PAGINAS)

    logger.info("Modalidade %d: %d publicações no período.", codigo_modalidade, len(itens))
    return itens


class PncpPortal(Portal):
    """Portal Nacional de Contratações Públicas."""

    nome = "pncp"

    def __init__(self, cache: CachePncp | None = None) -> None:
        self._cache = cache

    async def buscar(
        self,
        data_inicial: date,
        data_final: date,
        modalidades: list[int],
    ) -> list[Publicacao]:
        if data_final < data_inicial:
            raise ValueError("data_final deve ser posterior ou igual a data_inicial.")

        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
            publicacoes: list[dict[str, Any]] = []
            for codigo in modalidades:
                publicacoes.extend(
                    await _buscar_modalidade(client, data_inicial, data_final, codigo, self._cache)
                )
                await asyncio.sleep(PAUSA_ENTRE_PAGINAS)

        return [Publicacao.do_pncp(item) for item in publicacoes]


async def buscar_publicacoes(
    data_inicial: date,
    data_final: date,
    modalidades: list[int],
    cache: CachePncp | None = None,
) -> list[dict[str, Any]]:
    """Busca todas as contratações publicadas no período (backward compatible)."""
    portal = PncpPortal(cache=cache)
    publicacoes = await portal.buscar(data_inicial, data_final, modalidades)
    return [p.dados_raw for p in publicacoes]


def janela_padrao(hoje: date | None = None, dias: int = 2) -> tuple[date, date]:
    referencia = hoje or date.today()
    return referencia - timedelta(days=dias), referencia
