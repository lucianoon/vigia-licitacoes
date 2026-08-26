from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from vigia import cli
from vigia.config import Config, Perfil, Regra, TelegramConfig, WhatsAppConfig
from vigia.dashboard import _gerar_html
from vigia.portal import Publicacao
from vigia.store import Store


def _perfil() -> Perfil:
    return Perfil(
        nome="cliente-a",
        telegram=TelegramConfig(chat_id="tg"),
        whatsapp=WhatsAppConfig(chat_id="wa", api_url="http://wa"),
        regras=[Regra(nome="Ar", qualquer=["ar-condicionado"])],
    )


def test_lembrete_consulta_o_perfil_correto(tmp_path: Path) -> None:
    store = Store(str(tmp_path / "vigia.db"))
    store.marcar_alertados(["A"], perfil="cliente-a")
    antigo = (datetime.now() - timedelta(hours=25)).isoformat(timespec="seconds")
    store._con.execute(
        "UPDATE vistos SET visto_em = ? WHERE controle = ? AND perfil = ?",
        (antigo, "A", "cliente-a"),
    )
    store._con.commit()
    publicacao = Publicacao(
        controle="A",
        portal="pncp",
        objeto="manutencao de ar-condicionado",
        orgao="Prefeitura",
        uf="SP",
        modalidade="Pregao",
        data_encerramento=(datetime.now() + timedelta(hours=12)).isoformat(),
        dados_raw={"modalidadeId": 6},
    )

    encontrados = cli._processar_perfil(_perfil(), [publicacao], store, seco=False)

    assert len(encontrados) == 1
    assert encontrados[0][2] is True
    store.fechar()


async def test_so_retorna_controle_entregue(monkeypatch) -> None:
    async def whatsapp_enviar(
        api_url: str, token: str, chat_id: str, mensagens: list[str]
    ) -> int:
        return int(mensagens == ["ok"])

    async def telegram_falha(token: str, chat_id: str, mensagens: list[str]) -> int:
        raise RuntimeError("indisponivel")

    from vigia import whatsapp

    monkeypatch.setenv("WHATSAPP_API_TOKEN", "token")
    monkeypatch.setattr(whatsapp, "enviar", whatsapp_enviar)
    monkeypatch.setattr(cli.notify, "enviar", telegram_falha)

    entregues = await cli._enviar_notificacoes(
        _perfil(), ["ok", "falha"], ["A", "B"], "telegram-token", "all"
    )

    assert entregues == {"A"}


def test_historico_nao_troca_perfil_e_portal(tmp_path: Path) -> None:
    store = Store(str(tmp_path / "vigia.db"))
    store.marcar_alertados(
        ["A"], perfil="cliente-a", metadados=[{"portal": "pncp"}]
    )

    item = store.historico_alertas()[0]

    assert item["perfil"] == "cliente-a"
    assert item["portal"] == "pncp"
    store.fechar()


def test_migracao_preserva_historico_antigo(tmp_path: Path) -> None:
    caminho = tmp_path / "vigia.db"
    con = sqlite3.connect(caminho)
    con.execute(
        "CREATE TABLE vistos (controle TEXT PRIMARY KEY, visto_em TEXT, alertado INTEGER)"
    )
    con.execute("INSERT INTO vistos VALUES ('A', '2026-01-01T00:00:00', 1)")
    con.commit()
    con.close()

    store = Store(str(caminho))

    assert store.total() == 1
    assert store.nao_vistos(["A"]) == set()
    store.fechar()


def test_metricas_somam_quantidade_de_alertas(tmp_path: Path) -> None:
    store = Store(str(tmp_path / "vigia.db"))
    store.registrar_metrica("a", "alertas_enviados", "3")
    store.registrar_metrica("a", "alertas_enviados", "2")

    assert store.metricas()["alertas_enviados"] == 5
    assert store.metricas_por_perfil()["a"]["alertas_enviados"] == 5
    store.fechar()


def test_dashboard_escapa_dados_injetados_em_script() -> None:
    ataque = "</script><script>alert('x')</script>"

    pagina = _gerar_html(
        [{"objeto": ataque, "perfil": "a", "portal": "pncp"}],
        {},
        {},
        1,
        ["a"],
    )

    assert ataque not in pagina
    assert "\\u003c/script\\u003e" in pagina


def test_config_rejeita_portal_desconhecido() -> None:
    with pytest.raises(ValueError, match="portais desconhecidos"):
        Config(
            portais=["portal-inexistente"],
            regras=[Regra(nome="Ar", qualquer=["ar-condicionado"])],
        )
