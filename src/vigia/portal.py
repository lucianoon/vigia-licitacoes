from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass
class Publicacao:
    """Representação unificada de uma publicação de qualquer portal."""

    controle: str
    portal: str
    objeto: str
    orgao: str
    uf: str
    modalidade: str
    valor: float | None = None
    data_encerramento: str | None = None
    url: str | None = None
    dados_raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def do_pncp(cls, item: dict[str, Any]) -> Publicacao:
        orgao = (
            (item.get("orgaoEntidade") or {}).get("razaoSocial")
            or (item.get("unidadeOrgao") or {}).get("nomeUnidade")
            or ""
        )
        uf = str((item.get("unidadeOrgao") or {}).get("uf") or "").upper()
        modalidade = str(item.get("modalidadeNome") or "")
        controle = str(item.get("numeroControlePNCP") or "")
        numero = str(item.get("numeroCompra") or "")
        cnpj = str(item.get("cnpj") or "")
        ano = str(item.get("anoCompra") or "")
        url = (
            f"https://pncp.gov.br/app/editais/"
            f"{cnpj}-{ano.zfill(2)}-{numero.zfill(6)}/{ano}"
            if cnpj and numero
            else None
        )

        return cls(
            controle=controle,
            portal="pncp",
            objeto=str(item.get("objetoCompra") or ""),
            orgao=orgao,
            uf=uf,
            modalidade=modalidade,
            valor=item.get("valorTotalEstimado"),
            data_encerramento=str(item.get("dataEncerramentoProposta") or ""),
            url=url,
            dados_raw=item,
        )


class Portal(ABC):
    """Interface abstrata para portais de licitações."""

    nome: str

    @abstractmethod
    async def buscar(
        self,
        data_inicial: date,
        data_final: date,
        modalidades: list[int],
    ) -> list[Publicacao]:
        """Busca publicações do portal no período especificado."""
        ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} nome={self.nome!r}>"
