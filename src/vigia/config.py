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


class Config(BaseModel):
    perfil: dict[str, str] = {}
    telegram: TelegramConfig
    filtros_globais: FiltrosGlobais = FiltrosGlobais()
    regras: list[Regra]

    @classmethod
    def carregar(cls, caminho: str | None = None) -> "Config":
        import os

        candidatos = (
            [caminho] if caminho else [p for p in DEFAULT_PATHS]
        )
        arquivo: str | None = None
        for candidato in candidatos:
            expandido = os.path.expanduser(candidato)
            if os.path.exists(expandido):
                arquivo = expandido
                break
        if arquivo is None:
            procurados = ", ".join(DEFAULT_PATHS)
            raise FileNotFoundError(f"Configuração não encontrada. Procurei em: {procurados}")

        with open(arquivo, encoding="utf-8") as fh:
            dados = yaml.safe_load(fh) or {}

        try:
            config = cls.model_validate(dados)
        except ValidationError as exc:
            detalhes = "; ".join(
                f"{'.'.join(str(p) for p in erro['loc'])}: {erro['msg']}" for erro in exc.errors()
            )
            raise ValueError(f"{arquivo} inválido — {detalhes}") from exc

        if not config.regras:
            raise ValueError(f"{arquivo} não tem nenhuma regra definida.")
        return config
