from datetime import date

import httpx
import pytest
import respx

from vigia import notify, pncp
from vigia.matcher import ResultadoRegra

PNCP_URL = pncp.PNCP_URL


def _pagina(itens: list[dict], paginas_restantes: int) -> dict:
    return {"data": itens, "paginasRestantes": paginas_restantes, "totalRegistros": len(itens)}


def _item(controle: str = "SE123") -> dict:
    return {
        "numeroControlePNCP": controle,
        "numeroCompra": "PE 138",
        "anoCompra": 2026,
        "objetoCompra": "manutenção de climatização",
        "valorTotalEstimado": 60000.0,
        "modalidadeNome": "Pregão Eletrônico",
        "modalidadeId": 6,
        "dataEncerramentoProposta": "2099-09-04T14:00:01",
        "unidadeOrgao": {"uf": "SC", "municipio": "Itajaí", "nomeUnidade": "7º BBM"},
        "orgaoEntidade": {"razaoSocial": "Departamento de Bombeiros"},
    }


@respx.mock
async def test_buscar_publicacoes_pagina_ate_esgotar() -> None:
    rota = respx.get(PNCP_URL).mock(
        side_effect=[
            httpx.Response(
                200,
                json=_pagina([{"numeroControlePNCP": "A"} for _ in range(50)], 1),
            ),
            httpx.Response(200, json=_pagina([{"numeroControlePNCP": "B"}], 0)),
        ]
    )
    itens = await pncp.buscar_publicacoes(date(2026, 8, 25), date(2026, 8, 26), [6])

    assert len(itens) == 51
    assert rota.call_count == 2
    params_primeira = rota.calls[0].request.url.params
    assert params_primeira["dataInicial"] == "20260825"
    assert params_primeira["codigoModalidadeContratacao"] == "6"
    assert params_primeira["tamanhoPagina"] == "50"


async def test_janela_padrao() -> None:
    inicio, fim = pncp.janela_padrao(hoje=date(2026, 8, 26), dias=2)
    assert (inicio, fim) == (date(2026, 8, 24), date(2026, 8, 26))


@respx.mock
async def test_erro_http_vira_pncp_error() -> None:
    respx.get(PNCP_URL).mock(return_value=httpx.Response(503, text="fora do ar"))
    with pytest.raises(pncp.PncpError, match="503"):
        await pncp.buscar_publicacoes(date(2026, 8, 25), date(2026, 8, 26), [6])


def test_formatar_alerta_contem_campos_chave() -> None:
    resultado = ResultadoRegra(
        regra="Climatização",
        termos_casados=["bombas de calor"],
        destaques=["preventiva"],
    )
    saida = notify.formatar_alerta(_item(), resultado, "🤖 resumo curto")
    assert "PE 138/2026 · R$ 60.000" in saida
    assert "Itajaí/SC" in saida
    assert "Regra: Climatização" in saida
    assert "“bombas de calor”" in saida
    assert "Destaques: preventiva" in saida
    assert "resumo curto" in saida
    assert "https://pncp.gov.br/app/editais/SE123" in saida


def test_formatar_alerta_sem_prazo_nao_quebra() -> None:
    item = _item()
    item["dataEncerramentoProposta"] = None
    saida = notify.formatar_alerta(item, ResultadoRegra("R", ["climatização"], []), None)
    assert "ainda não informado" in saida


@respx.mock
async def test_enviar_telegram_sucesso() -> None:
    rota = respx.post("https://api.telegram.org/botTOKEN/sendMessage").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    enviadas = await notify.enviar("TOKEN", "42", ["msg um", "msg dois"])
    assert enviadas == 2
    corpo = rota.calls[0].request.read()
    assert b"msg um" in corpo


@respx.mock
async def test_enviar_telegram_erro_levanta_excecao() -> None:
    respx.post("https://api.telegram.org/botTOKEN/sendMessage").mock(
        return_value=httpx.Response(200, json={"ok": False, "description": "chat not found"})
    )
    with pytest.raises(notify.TelegramError, match="chat not found"):
        await notify.enviar("TOKEN", "42", ["oi"])
