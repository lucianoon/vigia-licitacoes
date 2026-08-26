import unicodedata
from dataclasses import dataclass, field
from typing import Any

from vigia.config import FiltrosGlobais, Regra


def normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto)
    ascii_texto = sem_acento.encode("ascii", "ignore").decode()
    return ascii_texto.casefold()


@dataclass
class ResultadoRegra:
    regra: str
    termos_casados: list[str] = field(default_factory=list)
    destaques: list[str] = field(default_factory=list)

    @property
    def score(self) -> int:
        return len(self.termos_casados) * 2 + len(self.destaques)


def _uf_do_item(item: dict[str, Any]) -> str:
    return str((item.get("unidadeOrgao") or {}).get("uf") or "").strip().upper()


def _orgao_do_item(item: dict[str, Any]) -> str:
    entidade = item.get("orgaoEntidade") or {}
    unidade = item.get("unidadeOrgao") or {}
    return normalizar(str(entidade.get("razaoSocial") or unidade.get("nomeUnidade") or ""))


def _valor_do_item(item: dict[str, Any]) -> float | None:
    valor = item.get("valorTotalEstimado")
    if isinstance(valor, int | float):
        return float(valor)
    return None


def passa_filtros_globais(item: dict[str, Any], filtros: FiltrosGlobais) -> bool:
    if filtros.ufs and _uf_do_item(item) not in {u.upper() for u in filtros.ufs}:
        return False

    orgao = _orgao_do_item(item)
    for excluido in filtros.excluir_orgaos:
        if normalizar(excluido) in orgao:
            return False

    valor = _valor_do_item(item)
    if valor is not None:
        if filtros.valor_minimo is not None and valor < filtros.valor_minimo:
            return False
        if filtros.valor_maximo is not None and valor > filtros.valor_maximo:
            return False

    return True


def avaliar_regra(objeto_normalizado: str, regra: Regra) -> ResultadoRegra | None:
    casados = [t for t in regra.qualquer if normalizar(t) in objeto_normalizado]
    if not casados:
        return None

    vetados = [t for t in regra.excluir if normalizar(t) in objeto_normalizado]
    if vetados:
        return None

    destaques = [d for d in regra.destaque if normalizar(d) in objeto_normalizado]
    resultado = ResultadoRegra(regra=regra.nome, termos_casados=casados, destaques=destaques)
    return resultado


def avaliar(
    item: dict[str, Any], filtros: FiltrosGlobais, regras: list[Regra]
) -> list[ResultadoRegra]:
    if not passa_filtros_globais(item, filtros):
        return []
    objeto_normalizado = normalizar(str(item.get("objetoCompra") or ""))
    if not objeto_normalizado:
        return []
    resultados = [r for r in (avaliar_regra(objeto_normalizado, regra) for regra in regras) if r]
    return sorted(resultados, key=lambda r: r.score, reverse=True)
