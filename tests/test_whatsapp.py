from __future__ import annotations

import httpx
import pytest
import respx

from vigia import whatsapp


@pytest.mark.parametrize(
    "api_url,api_token,chat_id",
    [
        ("", "token", "123"),
        ("http://x", "", "123"),
        ("http://x", "token", ""),
    ],
)
async def test_enviar_parametros_vazios_retorna_zero(
    api_url: str, api_token: str, chat_id: str
) -> None:
    assert await whatsapp.enviar(api_url, api_token, chat_id, ["oi"]) == 0


@respx.mock
async def test_enviar_sucesso() -> None:
    rota = respx.post("http://evo:8080/message/sendText/551199").mock(
        return_value=httpx.Response(200, json={"key": {"id": "abc"}})
    )
    enviadas = await whatsapp.enviar(
        "http://evo:8080", "token123", "551199", ["msg1", "msg2"]
    )
    assert enviadas == 2
    assert rota.call_count == 2


@respx.mock
async def test_enviar_http_erro_nao_envia() -> None:
    respx.post("http://evo:8080/message/sendText/551199").mock(
        return_value=httpx.Response(500, text="erro")
    )
    enviadas = await whatsapp.enviar(
        "http://evo:8080", "token", "551199", ["msg"]
    )
    assert enviadas == 0


@respx.mock
async def test_enviar_rate_limit_retries() -> None:
    rota = respx.post("http://evo:8080/message/sendText/551199").mock(
        side_effect=[
            httpx.Response(429, text="rate limited"),
            httpx.Response(429, text="rate limited"),
            httpx.Response(200, json={"ok": True}),
        ]
    )
    enviadas = await whatsapp.enviar(
        "http://evo:8080", "token", "551199", ["msg"]
    )
    assert enviadas == 1
    assert rota.call_count == 3


@respx.mock
async def test_enviar_timeout_levanta_excecao() -> None:
    respx.post("http://evo:8080/message/sendText/551199").mock(
        side_effect=httpx.ConnectError("connection refused")
    )
    enviadas = await whatsapp.enviar(
        "http://evo:8080", "token", "551199", ["msg"]
    )
    assert enviadas == 0
