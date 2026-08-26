from __future__ import annotations

from typing import Any

import yaml
from pydantic import BaseModel, ValidationError

DEFAULT_PATHS = ("vigia.yaml", "~/.config/vigia/vigia.yaml")


class TelegramConfig(BaseModel):
    chat_id: str


class FiltrosGlobais(BaseModel):
    ufs: list[str] = []
    valor_minimo: float | None = None
    valor_maximo: float | None = None
    modalidades: list[int] = [6]
    excluir_orgaos: list[str] = []


class Regra(BaseModel):
    nome: str
    qualquer: list[str] = []
    excluir: list[str] = []
    destaque: list[str] = []


class Perfil(BaseModel):
    nome: str
    telegram: TelegramConfig
    regras: list[Regra]
    filtros_globais: FiltrosGlobais = FiltrosGlobais()


class Config(BaseModel):
    perfil: dict[str, str] = {}
    telegram: TelegramConfig = TelegramConfig(chat_id="")
    filtros_globais: FiltrosGlobais = FiltrosGlobais()
    regras: list[Regra] = []
    perfis: list[Perfil] = []

    def perfis_resolvidos(self) -> list[Perfil]:
        if self.perfis:
            return self.perfis
        return [
            Perfil(
                nome=self.perfil.get("nome", "Padrao"),
                telegram=self.telegram,
                regras=self.regras,
                filtros_globais=self.filtros_globais,
            )
        ]

    @classmethod
    def carregar(cls, caminho: str | None = None) -> Config:
        import os

        candidatos = [caminho] if caminho else list(DEFAULT_PATHS)
        arquivo: str | None = None
        for candidato in candidatos:
            expandido = os.path.expanduser(candidato)
            if os.path.exists(expandido):
                arquivo = expandido
                break
        if arquivo is None:
            procurados = ", ".join(DEFAULT_PATHS)
            raise FileNotFoundError(
                f"Configuracao nao encontrada. Procurei em: {procurados}"
            )

        with open(arquivo, encoding="utf-8") as fh:
            dados = yaml.safe_load(fh) or {}

        dados = _normalizar_perfis(dados, arquivo)

        try:
            config = cls.model_validate(dados)
        except ValidationError as exc:
            detalhes = "; ".join(
                f"{'.'.join(str(p) for p in erro['loc'])}: {erro['msg']}"
                for erro in exc.errors()
            )
            raise ValueError(f"{arquivo} invalido -- {detalhes}") from exc

        perfis = config.perfis_resolvidos()
        if not perfis or not any(p.regras for p in perfis):
            raise ValueError(f"{arquivo} nao tem nenhuma regra definida.")
        return config


def _normalizar_perfis(dados: dict[str, Any], arquivo: str) -> dict[str, Any]:
    if "perfis" in dados:
        filtros_raiz = dados.get("filtros_globais", {})
        for perfil in dados["perfis"]:
            if "filtros_globais" not in perfil:
                perfil["filtros_globais"] = dict(filtros_raiz)
            else:
                mesclados = dict(filtros_raiz)
                mesclados.update(perfil["filtros_globais"])
                perfil["filtros_globais"] = mesclados
        return dados
    if "regras" not in dados:
        return dados

    perfis: list[dict[str, Any]] = []
    perfil_raiz: dict[str, Any] = {}

    for chave in ("nome", "descricao", "empresa"):
        if chave in dados.get("perfil", {}):
            perfil_raiz[chave] = dados["perfil"][chave]
    perfil_raiz.setdefault("nome", "Padrao")

    if "telegram" in dados:
        perfil_raiz["telegram"] = dados["telegram"]
    if "regras" in dados:
        perfil_raiz["regras"] = dados["regras"]
    if "filtros_globais" in dados:
        perfil_raiz["filtros_globais"] = dados["filtros_globais"]

    perfis.append(perfil_raiz)
    dados["perfis"] = perfis

    return dados
