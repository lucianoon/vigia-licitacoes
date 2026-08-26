import sqlite3
from datetime import datetime
from pathlib import Path


class Store:
    def __init__(self, caminho: str = "vigia.db") -> None:
        self.caminho = Path(caminho)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self._con = self._conectar()

    def _conectar(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.caminho)
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS vistos (
                controle TEXT PRIMARY KEY,
                visto_em TEXT NOT NULL,
                alertado INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        con.commit()
        return con

    def nao_vistos(self, controles: list[str]) -> set[str]:
        if not controles:
            return set()
        placeholders = ",".join("?" for _ in controles)
        consulta = (
            f"SELECT controle FROM vistos WHERE controle IN ({placeholders})"  # noqa: S608
        )
        linhas = self._con.execute(consulta, controles).fetchall()
        encontrados = {linha[0] for linha in linhas}
        return set(controles) - encontrados

    def marcar_alertados(self, controles: list[str]) -> None:
        agora = datetime.now().isoformat(timespec="seconds")
        self._con.executemany(
            "INSERT OR IGNORE INTO vistos (controle, visto_em, alertado) VALUES (?, ?, 1)",
            [(controle, agora) for controle in controles],
        )
        self._con.commit()

    def total(self) -> int:
        linha = self._con.execute("SELECT COUNT(*) FROM vistos").fetchone()
        return int(linha[0])

    def fechar(self) -> None:
        self._con.close()
