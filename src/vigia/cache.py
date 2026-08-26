from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

TTL_PADRAO = timedelta(hours=4)

SCHEMA_CACHE = """
CREATE TABLE IF NOT EXISTS cache_pncp (
    chave TEXT PRIMARY KEY,
    dados TEXT NOT NULL,
    criado_em TEXT NOT NULL
)
"""


class CachePncp:
    def __init__(
        self,
        caminho: str = "vigia.db",
        ttl: timedelta = TTL_PADRAO,
    ) -> None:
        self.caminho = Path(caminho)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl
        self._con = self._conectar()

    def _conectar(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.caminho)
        con.execute(SCHEMA_CACHE)
        con.commit()
        return con

    def _chave(
        self,
        data_inicial: str,
        data_final: str,
        modalidades: list[int],
        pagina: int,
        tamanho: int,
    ) -> str:
        payload = f"{data_inicial}:{data_final}:{sorted(modalidades)}:{pagina}:{tamanho}"
        return hashlib.sha256(payload.encode()).hexdigest()[:32]

    def buscar(
        self,
        data_inicial: str,
        data_final: str,
        modalidades: list[int],
        pagina: int,
        tamanho: int,
    ) -> dict[str, Any] | None:
        chave = self._chave(data_inicial, data_final, modalidades, pagina, tamanho)
        linha = self._con.execute(
            "SELECT dados, criado_em FROM cache_pncp WHERE chave = ?",
            (chave,),
        ).fetchone()
        if not linha:
            return None
        criado = datetime.fromisoformat(linha[1])
        if datetime.now() - criado > self.ttl:
            self._con.execute("DELETE FROM cache_pncp WHERE chave = ?", (chave,))
            self._con.commit()
            return None
        dados_json: str = linha[0]
        resultado: dict[str, Any] = json.loads(dados_json)
        return resultado

    def salvar(
        self,
        data_inicial: str,
        data_final: str,
        modalidades: list[int],
        pagina: int,
        tamanho: int,
        dados: dict[str, Any],
    ) -> None:
        chave = self._chave(data_inicial, data_final, modalidades, pagina, tamanho)
        agora = datetime.now().isoformat(timespec="seconds")
        self._con.execute(
            "INSERT OR REPLACE INTO cache_pncp (chave, dados, criado_em) VALUES (?, ?, ?)",
            (chave, json.dumps(dados, ensure_ascii=False), agora),
        )
        self._con.commit()

    def limpar_expirados(self) -> int:
        limite = (datetime.now() - self.ttl).isoformat(timespec="seconds")
        cursor = self._con.execute(
            "DELETE FROM cache_pncp WHERE criado_em < ?", (limite,)
        )
        self._con.commit()
        return cursor.rowcount

    def total(self) -> int:
        linha = self._con.execute("SELECT COUNT(*) FROM cache_pncp").fetchone()
        return int(linha[0])

    def fechar(self) -> None:
        self._con.close()
