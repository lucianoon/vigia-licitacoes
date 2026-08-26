from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Any

import httpx

from vigia.portal import Portal, Publicacao

logger = logging.getLogger(__name__)

PETRONECT_URL = (
    "https://www.petronect.com.br/wps/portal/licitacoes/api/v1/licitacoes"
)
PAUSA = 2.0
TENTATIVAS = 3


class PetronectPortal(Portal):
    """Portal de licitações da Petrobras (Petronect)."""

    nome = "petronect"

    async def buscar(
        self,
        data_inicial: date,
        data_final: date,
        modalidades: list[int],
    ) -> list[Publicacao]:
        params = {
            "dataInicio": data_inicial.strftime("%d/%m/%Y"),
            "dataFim": data_final.strftime("%d/%m/%Y"),
            "pagina": "1",
            "tamanhoPagina": "50",
        }

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers={
                "Accept": "application/json",
                "User-Agent": "Vigia/0.2",
            },
        ) as client:
            for tentativa in range(TENTATIVAS):
                try:
                    resposta = await client.get(
                        PETRONECT_URL, params=params
                    )
                    if resposta.status_code == 200:
                        dados = resposta.json()
                        itens = (
                            dados.get("data")
                            or dados.get("licitacoes")
                            or []
                        )
                        if isinstance(itens, list):
                            return [
                                self._converter(item)
                                for item in itens
                                if isinstance(item, dict)
                            ]
                        return []
                    if resposta.status_code in (429, 502, 503, 504):
                        logger.warning(
                            "Petronect HTTP %d (tentativa %d/%d)",
                            resposta.status_code,
                            tentativa + 1,
                            TENTATIVAS,
                        )
                        await asyncio.sleep(5.0 * (tentativa + 1))
                        continue
                    logger.warning(
                        "Petronect HTTP %d", resposta.status_code
                    )
                    return []
                except (httpx.TransportError, ValueError) as exc:
                    logger.warning(
                        "Petronect falhou (tentativa %d/%d): %r",
                        tentativa + 1,
                        TENTATIVAS,
                        exc,
                    )
                    if tentativa < TENTATIVAS - 1:
                        await asyncio.sleep(3.0 * (tentativa + 1))

        logger.warning(
            "Petronect indisponivel apos %d tentativas. Retornando vazio.",
            TENTATIVAS,
        )
        return []

    def _converter(self, item: dict[str, Any]) -> Publicacao:
        return Publicacao(
            controle=str(
                item.get("id") or item.get("numeroControle") or ""
            ),
            portal="petronect",
            objeto=str(
                item.get("objeto") or item.get("descricao") or ""
            ),
            orgao=str(
                item.get("orgao") or item.get("unidade") or "Petrobras"
            ),
            uf=str(item.get("uf") or "SP").upper(),
            modalidade=str(item.get("modalidade") or ""),
            valor=_parse_valor(item.get("valorEstimado")),
            data_encerramento=str(
                item.get("dataEncerramento") or ""
            ),
            url=str(item.get("url") or ""),
            dados_raw=item,
        )


def _parse_valor(valor: Any) -> float | None:
    if isinstance(valor, (int, float)):
        return float(valor)
    if isinstance(valor, str):
        texto = (
            valor.replace("R$", "")
            .replace(".", "")
            .replace(",", ".")
            .strip()
        )
        try:
            return float(texto)
        except ValueError:
            return None
    return None
