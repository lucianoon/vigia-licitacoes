import httpx
import pytest
import respx

from vigia.llm import resumir
from vigia.store import Store

LLM_URL = "https://api.openai.com/v1/chat/completions"


async def test_resumir_sem_api_key_retorna_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert await resumir({"objetoCompra": "x"}) is None


@respx.mock
async def test_resumir_sucesso(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-teste")
    respx.post(LLM_URL).mock(
        return_value=httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Compra de bombas para piscina."}}]},
        )
    )
    saida = await resumir({"objetoCompra": "bombas de calor"})
    assert saida == "Compra de bombas para piscina."


@respx.mock
async def test_resumir_falha_da_api_retorna_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-teste")
    respx.post(LLM_URL).mock(return_value=httpx.Response(500, text="boom"))
    assert await resumir({"objetoCompra": "bombas"}) is None


def test_store_dedup(tmp_path) -> None:
    store = Store(str(tmp_path / "vigia.db"))
    try:
        assert store.nao_vistos(["A", "B"]) == {"A", "B"}
        store.marcar_alertados(["A"])
        assert store.nao_vistos(["A", "B"]) == {"B"}
        store.marcar_alertados(["A"])
        assert store.total() == 1
    finally:
        store.fechar()


def test_store_pode_lembrar_false_recem_alertado(tmp_path) -> None:
    store = Store(str(tmp_path / "vigia.db"))
    try:
        store.marcar_alertados(["X"])
        assert not store.pode_lembrar("X")
    finally:
        store.fechar()


def test_store_pode_lembrar_true_apos_24h(tmp_path) -> None:
    from datetime import datetime, timedelta

    store = Store(str(tmp_path / "vigia.db"))
    try:
        store.marcar_alertados(["Y"])
        # Simular visto_em antigo (25h atras)
        antigo = (datetime.now() - timedelta(hours=25)).isoformat(timespec="seconds")
        store._con.execute(
            "UPDATE vistos SET visto_em = ? WHERE controle = 'Y'",
            (antigo,),
        )
        store._con.commit()
        assert store.pode_lembrar("Y")
    finally:
        store.fechar()


def test_store_pode_lembrar_false_nao_visto(tmp_path) -> None:
    store = Store(str(tmp_path / "vigia.db"))
    try:
        assert not store.pode_lembrar("Z")
    finally:
        store.fechar()
