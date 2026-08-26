import pytest

from vigia.config import Config, FiltrosGlobais, Regra
from vigia.matcher import avaliar, avaliar_regra, normalizar, passa_filtros_globais


def _item(
    objeto: str = "manutenção de ar-condicionado",
    uf: str = "SC",
    valor: float | None = 60000.0,
    orgao: str = "7º Batalhão de Bombeiros",
) -> dict:
    return {
        "objetoCompra": objeto,
        "valorTotalEstimado": valor,
        "unidadeOrgao": {"uf": uf, "nomeUnidade": orgao},
        "orgaoEntidade": {"razaoSocial": orgao},
    }


FILTROS_VAZIOS = FiltrosGlobais()


def test_normalizar_remove_acentos_e_minusculas() -> None:
    assert normalizar("CLIMATIZAÇÃO Ar-Condicionado") == "climatizacao ar-condicionado"


def test_regra_casa_por_qualquer_termo() -> None:
    regra = Regra(nome="Clima", qualquer=["ar condicionado", "ar-condicionado"])
    resultado = avaliar_regra(normalizar(_item()["objetoCompra"]), regra)
    assert resultado is not None
    assert resultado.regra == "Clima"
    assert resultado.termos_casados == ["ar-condicionado"]


def test_regra_nao_casa_sem_termo() -> None:
    regra = Regra(nome="Elétrica", qualquer=["quadro de distribuição"])
    assert avaliar_regra("pintura de muros", regra) is None


def test_excluir_veta_o_match() -> None:
    regra = Regra(nome="Clima", qualquer=["climatização"], excluir=["locação de imóvel"])
    assert avaliar_regra(normalizar("climatização de locação de imóvel"), regra) is None


def test_destaque_aumenta_score_sem_obrigar() -> None:
    base = Regra(nome="X", qualquer=["climatização"])
    com_destaque = Regra(nome="X", qualquer=["climatização"], destaque=["preventiva"])
    r1 = avaliar_regra(normalizar("climatização simples"), base)
    r2 = avaliar_regra(normalizar("climatização preventiva"), com_destaque)
    assert r1 and r2
    assert r2.score > r1.score


def test_filtros_globais_uf() -> None:
    filtros = FiltrosGlobais(ufs=["PR"])
    assert not passa_filtros_globais(_item(uf="SC"), filtros)
    assert passa_filtros_globais(_item(uf="PR"), filtros)


def test_filtros_globais_valor() -> None:
    filtros = FiltrosGlobais(valor_minimo=100000.0)
    assert not passa_filtros_globais(_item(valor=60000.0), filtros)
    filtros_max = FiltrosGlobais(valor_maximo=50000.0)
    assert not passa_filtros_globais(_item(valor=60000.0), filtros_max)
    assert passa_filtros_globais(_item(valor=None), filtros)


def test_filtros_globais_excluir_orgao() -> None:
    filtros = FiltrosGlobais(excluir_orgaos=["câmara municipal"])
    assert not passa_filtros_globais(_item(orgao="Câmara Municipal de X"), filtros)


def test_avaliar_ordena_por_score_e_aplica_filtros() -> None:
    filtros = FiltrosGlobais(ufs=["SC"])
    regras = [
        Regra(nome="Fraca", qualquer=["equipamentos"]),
        Regra(nome="Forte", qualquer=["manutenção"], destaque=["preventiva"]),
    ]
    item = _item(objeto="Manutenção preventiva de equipamentos")
    resultados = avaliar(item, filtros, regras)
    assert [r.regra for r in resultados] == ["Forte", "Fraca"]


def test_avaliar_item_fora_dos_filtros_retorna_vazio() -> None:
    regras = [Regra(nome="X", qualquer=["manutenção"])]
    assert avaliar(_item(uf="AM"), FiltrosGlobais(ufs=["SC"]), regras) == []


@pytest.mark.parametrize(
    ("dados", "esperado"),
    [
        ({"telegram": {"chat_id": "1"}, "regras": [{"nome": "A", "qualquer": ["x"]}]}, True),
        ({"telegram": {"chat_id": "1"}, "regras": []}, False),
        ({"telegram": {"chat_id": "1"}}, False),
    ],
)
def test_config_validacao(tmp_path, dados: dict, esperado: bool) -> None:
    import yaml

    arquivo = tmp_path / "vigia.yaml"
    arquivo.write_text(yaml.safe_dump(dados), encoding="utf-8")
    try:
        Config.carregar(str(arquivo))
        valido = True
    except (ValueError, FileNotFoundError):
        valido = False
    assert valido is esperado


# ── Multi-perfil ──────────────────────────────────────────────


def _escrever_config(tmp_path, dados):
    import yaml

    arquivo = tmp_path / "vigia.yaml"
    arquivo.write_text(yaml.safe_dump(dados), encoding="utf-8")
    return str(arquivo)


def test_config_legacy_retorna_single_perfil(tmp_path):
    dados = {
        "telegram": {"chat_id": "111"},
        "regras": [{"nome": "R1", "qualquer": ["x"]}],
    }
    caminho = _escrever_config(tmp_path, dados)
    config = Config.carregar(caminho)
    perfis = config.perfis_resolvidos()
    assert len(perfis) == 1
    assert perfis[0].nome == "Padrao"
    assert perfis[0].telegram.chat_id == "111"
    assert len(perfis[0].regras) == 1


def test_config_multi_perfil(tmp_path):
    dados = {
        "filtros_globais": {"valor_minimo": 10000},
        "perfis": [
            {
                "nome": "A",
                "telegram": {"chat_id": "111"},
                "regras": [{"nome": "R1", "qualquer": ["x"]}],
            },
            {
                "nome": "B",
                "telegram": {"chat_id": "222"},
                "regras": [{"nome": "R2", "qualquer": ["y"]}],
            },
        ],
    }
    caminho = _escrever_config(tmp_path, dados)
    config = Config.carregar(caminho)
    perfis = config.perfis_resolvidos()
    assert len(perfis) == 2
    assert perfis[0].nome == "A"
    assert perfis[1].nome == "B"
    assert perfis[0].telegram.chat_id == "111"
    assert perfis[1].telegram.chat_id == "222"


def test_config_perfil_herda_filtros_globais(tmp_path):
    dados = {
        "filtros_globais": {"valor_minimo": 50000, "ufs": ["SP"]},
        "perfis": [
            {
                "nome": "A",
                "telegram": {"chat_id": "111"},
                "regras": [{"nome": "R1", "qualquer": ["x"]}],
            },
        ],
    }
    caminho = _escrever_config(tmp_path, dados)
    config = Config.carregar(caminho)
    perfil = config.perfis_resolvidos()[0]
    assert perfil.filtros_globais.valor_minimo == 50000
    assert perfil.filtros_globais.ufs == ["SP"]


def test_config_perfil_sobrescreve_filtros(tmp_path):
    dados = {
        "filtros_globais": {"valor_minimo": 50000, "ufs": ["SP"]},
        "perfis": [
            {
                "nome": "A",
                "telegram": {"chat_id": "111"},
                "regras": [{"nome": "R1", "qualquer": ["x"]}],
                "filtros_globais": {"ufs": ["RJ"], "valor_minimo": 200000},
            },
        ],
    }
    caminho = _escrever_config(tmp_path, dados)
    config = Config.carregar(caminho)
    perfil = config.perfis_resolvidos()[0]
    assert perfil.filtros_globais.ufs == ["RJ"]
    assert perfil.filtros_globais.valor_minimo == 200000


def test_config_multi_perfil_legacy_e_perfis_coexistem(tmp_path):
    """Se perfis esta presente, regras raiz sao ignoradas."""
    dados = {
        "telegram": {"chat_id": "999"},
        "regras": [{"nome": "Old", "qualquer": ["z"]}],
        "perfis": [
            {
                "nome": "Novo",
                "telegram": {"chat_id": "111"},
                "regras": [{"nome": "R1", "qualquer": ["x"]}],
            },
        ],
    }
    caminho = _escrever_config(tmp_path, dados)
    config = Config.carregar(caminho)
    perfis = config.perfis_resolvidos()
    assert len(perfis) == 1
    assert perfis[0].nome == "Novo"


def test_config_multi_perfil_vazio_rejeitado(tmp_path):
    dados = {
        "perfis": [
            {
                "nome": "A",
                "telegram": {"chat_id": "111"},
                "regras": [],
            },
        ],
    }
    caminho = _escrever_config(tmp_path, dados)
    with pytest.raises(ValueError, match="nenhuma regra"):
        Config.carregar(caminho)
