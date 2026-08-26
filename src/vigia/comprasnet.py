from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Any

import httpx

from vigia.portal import Portal, Publicacao

logger = logging.getLogger(__name__)

PAUSA = 2.0


class ComprasNetPortal(Portal):
    """Portal de compras federais (ComprasNet/Compras.gov.br).

    ComprasNet é integrado ao PNCP desde 2025. Usa a mesma API.
    """

    nome = "comprasnet"

    async def buscar(
        self,
        data_inicial: date,
        data_final: date,
        modalidades: list[int],
    ) -> list[Publicacao]:
        from vigia.pncp import _buscar_modalidade

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=10.0)
        ) as client:
            publicacoes_raw: list[dict[str, Any]] = []
            for codigo in modalidades:
                publicacoes_raw.extend(
                    await _buscar_modalidade(
                        client, data_inicial, data_final, codigo
                    )
                )
                await asyncio.sleep(PAUSA)

        return [
            self._converter(item)
            for item in publicacoes_raw
            if isinstance(item, dict)
        ]

    def _converter(self, item: dict[str, Any]) -> Publicacao:
        orgao = (
            (item.get("orgaoEntidade") or {}).get("razaoSocial")
            or (item.get("unidadeOrgao") or {}).get("nomeUnidade")
            or ""
        )
        return Publicacao(
            controle=str(item.get("numeroControlePNCP") or ""),
            portal="comprasnet",
            objeto=str(item.get("objetoCompra") or ""),
            orgao=orgao,
            uf=str(
                (item.get("unidadeOrgao") or {}).get("uf") or ""
            ).upper(),
            modalidade=str(item.get("modalidadeNome") or ""),
            valor=item.get("valorTotalEstimado"),
            data_encerramento=str(
                item.get("dataEncerramentoProposta") or ""
            ),
            dados_raw=item,
        )
