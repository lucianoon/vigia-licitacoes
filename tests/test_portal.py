from __future__ import annotations

from vigia.portal import Publicacao


def test_publicacao_campos_obrigatorios() -> None:
    pub = Publicacao(
        controle="PE123",
        portal="pncp",
        objeto="Manutencao de ar",
        orgao="Prefeitura",
        uf="SP",
        modalidade="Pregao",
    )
    assert pub.controle == "PE123"
    assert pub.portal == "pncp"
    assert pub.valor is None
    assert pub.url is None
    assert pub.dados_raw == {}


def test_publicacao_do_pncp() -> None:
    item = {
        "numeroControlePNCP": "PE456",
        "numeroCompra": "PE 138",
        "objetoCompra": "Compra de bombas",
        "valorTotalEstimado": 80000.0,
        "modalidadeNome": "Pregao Eletronico",
        "dataEncerramentoProposta": "2026-09-01T10:00:00",
        "cnpj": "12345678000199",
        "anoCompra": 2026,
        "unidadeOrgao": {"uf": "RJ", "nomeUnidade": "Sec. Saude"},
        "orgaoEntidade": {"razaoSocial": "Municipio do RJ"},
    }
    pub = Publicacao.do_pncp(item)
    assert pub.controle == "PE456"
    assert pub.portal == "pncp"
    assert pub.valor == 80000.0
    assert pub.uf == "RJ"
    assert pub.orgao == "Municipio do RJ"
    assert pub.url is not None
    assert "12345678000199" in pub.url


def test_publicacao_do_pncp_campos_faltando() -> None:
    pub = Publicacao.do_pncp({})
    assert pub.controle == ""
    assert pub.uf == ""
    assert pub.valor is None
    assert pub.url is None


def test_publicacao_do_pncp_url_completa() -> None:
    item = {
        "numeroControlePNCP": "PE789",
        "cnpj": "11111111000111",
        "anoCompra": 2025,
        "numeroCompra": "PE 100",
    }
    pub = Publicacao.do_pncp(item)
    assert "/app/editais/" in pub.url
    assert "11111111000111" in pub.url
