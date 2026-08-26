from __future__ import annotations

import asyncio
import time

from vigia.portal import Publicacao


def _pub(controle: str) -> Publicacao:
    return Publicacao(
        controle=controle,
        portal="pncp",
        objeto="teste",
        orgao="orgao",
        uf="SP",
        modalidade="Pregao",
    )


async def test_gather_processa_em_paralelo() -> None:
    """asyncio.gather executa coroutines em paralelo."""
    resultados = []

    async def _tarefa(nome: str, delay: float) -> str:
        await asyncio.sleep(delay)
        resultados.append(nome)
        return nome

    inicio = time.monotonic()
    await asyncio.gather(
        _tarefa("A", 0.05),
        _tarefa("B", 0.05),
        _tarefa("C", 0.05),
    )
    duracao = time.monotonic() - inicio

    assert set(resultados) == {"A", "B", "C"}
    assert duracao < 0.15


async def test_gather_erro_nao_bloqueia_outros() -> None:
    async def _ok() -> str:
        return "ok"

    async def _erro() -> str:
        raise RuntimeError("falha")

    resultados = await asyncio.gather(_ok(), _erro(), _ok(), return_exceptions=True)
    erros = [r for r in resultados if isinstance(r, Exception)]
    ok = [r for r in resultados if r == "ok"]
    assert len(erros) == 1
    assert len(ok) == 2


async def test_gather_return_exceptions_true() -> None:
    async def _boom() -> None:
        raise ValueError("x")

    resultados = await asyncio.gather(_boom(), _boom(), return_exceptions=True)
    assert all(isinstance(r, ValueError) for r in resultados)
