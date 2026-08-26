from __future__ import annotations

import logging
from typing import Any

from vigia.portal import Portal

logger = logging.getLogger(__name__)

_PORTAIS_DISPONIVEIS: dict[str, type[Portal]] = {}


def registrar(portal_cls: type[Portal]) -> type[Portal]:
    """Registra um portal na factory."""
    _PORTAIS_DISPONIVEIS[portal_cls.nome] = portal_cls
    return portal_cls


def criar_portais(
    nomes: list[str] | None = None,
    **kwargs: Any,
) -> list[Portal]:
    """Cria instâncias dos portais solicitados.

    Se nomes for None ou vazio, retorna apenas PNCP (default).
    kwargs são passados como argumentos de construção (ex: cache=).
    """
    if nomes is None:
        nomes = []

    if not nomes:
        nomes = ["pncp"]

    portais: list[Portal] = []
    for nome in nomes:
        cls = _PORTAIS_DISPONIVEIS.get(nome)
        if cls is None:
            logger.warning("Portal desconhecido: %s (ignorando)", nome)
            continue
        try:
            portais.append(cls(**kwargs))
        except TypeError:
            portais.append(cls())
    return portais


def portais_disponiveis() -> list[str]:
    """Retorna nomes de todos os portais registrados."""
    return sorted(_PORTAIS_DISPONIVEIS.keys())


def _registrar_portais_padrao() -> None:
    """Registra portais built-in."""
    from vigia.comprasnet import ComprasNetPortal
    from vigia.pncp import PncpPortal

    registrar(PncpPortal)
    registrar(ComprasNetPortal)


_registrar_portais_padrao()
