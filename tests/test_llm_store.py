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
