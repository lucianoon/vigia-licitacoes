import sqlite3
from datetime import datetime
from pathlib import Path

SCHEMA_VISTOS = """
CREATE TABLE IF NOT EXISTS vistos (
    controle TEXT NOT NULL,
    perfil TEXT NOT NULL DEFAULT '__global__',
    visto_em TEXT NOT NULL,
    alertado INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (controle, perfil)
)
"""


class Store:
    def __init__(self, caminho: str = "vigia.db") -> None:
        self.caminho = Path(caminho)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self._con = self._conectar()

    def _conectar(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.caminho)
        con.execute(SCHEMA_VISTOS)
        # Migracao: schema antigo (PK so em controle) → novo (controle+perfil)
        try:
            con.execute("SELECT perfil FROM vistos LIMIT 1")
        except sqlite3.OperationalError:
            con.execute("DROP TABLE IF EXISTS vistos")
            con.execute(SCHEMA_VISTOS)
        con.commit()
        return con

    def nao_vistos(
        self, controles: list[str], perfil: str = "__global__"
    ) -> set[str]:
        if not controles:
            return set()
        placeholders = ",".join("?" for _ in controles)
        consulta = f"SELECT controle FROM vistos WHERE perfil = ? AND controle IN ({placeholders})"  # noqa: S608
        linhas = self._con.execute(consulta, [perfil, *controles]).fetchall()
        encontrados = {linha[0] for linha in linhas}
        return set(controles) - encontrados

    def marcar_alertados(
        self, controles: list[str], perfil: str = "__global__"
    ) -> None:
        agora = datetime.now().isoformat(timespec="seconds")
        self._con.executemany(
            "INSERT OR IGNORE INTO vistos (controle, perfil, visto_em, alertado) "
            "VALUES (?, ?, ?, 1)",
            [(controle, perfil, agora) for controle in controles],
        )
        self._con.commit()

    def total(self, perfil: str | None = None) -> int:
        if perfil:
            linha = self._con.execute(
                "SELECT COUNT(*) FROM vistos WHERE perfil = ?", (perfil,)
            ).fetchone()
        else:
            linha = self._con.execute("SELECT COUNT(*) FROM vistos").fetchone()
        return int(linha[0])

    def fechar(self) -> None:
        self._con.close()
