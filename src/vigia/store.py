from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

SCHEMA_VISTOS = """
CREATE TABLE IF NOT EXISTS vistos (
    controle TEXT NOT NULL,
    perfil TEXT NOT NULL DEFAULT '__global__',
    visto_em TEXT NOT NULL,
    alertado INTEGER NOT NULL DEFAULT 0,
    semana TEXT NOT NULL DEFAULT '',
    objeto TEXT NOT NULL DEFAULT '',
    valor REAL,
    regra TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (controle, perfil)
)
"""

SCHEMA_METRICAS = """
CREATE TABLE IF NOT EXISTS metricas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    perfil TEXT NOT NULL,
    evento TEXT NOT NULL,
    detalhe TEXT NOT NULL DEFAULT '',
    criado_em TEXT NOT NULL
)
"""

INTERVALO_LEMBRETE = timedelta(hours=24)


class Store:
    def __init__(self, caminho: str = "vigia.db") -> None:
        self.caminho = Path(caminho)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self._con = self._conectar()

    def _conectar(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.caminho)
        con.execute(SCHEMA_VISTOS)
        con.execute(SCHEMA_METRICAS)
        try:
            con.execute("SELECT semana FROM vistos LIMIT 1")
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

    def pode_lembrar(self, controle: str, perfil: str = "__global__") -> bool:
        linha = self._con.execute(
            "SELECT visto_em FROM vistos WHERE controle = ? AND perfil = ?",
            (controle, perfil),
        ).fetchone()
        if not linha:
            return False
        try:
            ultimo = datetime.fromisoformat(linha[0])
        except ValueError:
            return False
        return datetime.now() - ultimo >= INTERVALO_LEMBRETE

    def marcar_alertados(
        self,
        controles: list[str],
        perfil: str = "__global__",
        metadados: list[dict[str, Any]] | None = None,
    ) -> None:
        agora = datetime.now().isoformat(timespec="seconds")
        semana = datetime.now().strftime("%G-W%V")
        linhas = []
        for i, controle in enumerate(controles):
            meta = (metadados[i] if metadados and i < len(metadados) else {}) or {}
            linhas.append((
                controle,
                perfil,
                agora,
                semana,
                meta.get("objeto", ""),
                meta.get("valor"),
                meta.get("regra", ""),
            ))
        self._con.executemany(
            "INSERT INTO vistos "
            "(controle, perfil, visto_em, alertado, semana, objeto, valor, regra) "
            "VALUES (?, ?, ?, 1, ?, ?, ?, ?) "
            "ON CONFLICT(controle, perfil) DO UPDATE SET "
            "visto_em = ?, alertado = 1, semana = ?, objeto = ?, valor = ?, regra = ?",
            [
                (*row, row[2], row[3], row[4], row[5], row[6])
                for row in linhas
            ],
        )
        self._con.commit()

    def registrar_metrica(self, perfil: str, evento: str, detalhe: str = "") -> None:
        agora = datetime.now().isoformat(timespec="seconds")
        self._con.execute(
            "INSERT INTO metricas (perfil, evento, detalhe, criado_em) VALUES (?, ?, ?, ?)",
            (perfil, evento, detalhe, agora),
        )
        self._con.commit()

    def metricas(
        self, perfil: str | None = None, dias: int = 30
    ) -> dict[str, Any]:
        desde = (datetime.now() - timedelta(days=dias)).isoformat(timespec="seconds")
        if perfil:
            linhas = self._con.execute(
                "SELECT evento, COUNT(*) FROM metricas "
                "WHERE perfil = ? AND criado_em >= ? GROUP BY evento",
                (perfil, desde),
            ).fetchall()
        else:
            linhas = self._con.execute(
                "SELECT evento, COUNT(*) FROM metricas WHERE criado_em >= ? GROUP BY evento",
                (desde,),
            ).fetchall()
        return {row[0]: row[1] for row in linhas}

    def metricas_por_perfil(self, dias: int = 30) -> dict[str, dict[str, int]]:
        desde = (datetime.now() - timedelta(days=dias)).isoformat(timespec="seconds")
        linhas = self._con.execute(
            "SELECT perfil, evento, COUNT(*) FROM metricas "
            "WHERE criado_em >= ? GROUP BY perfil, evento",
            (desde,),
        ).fetchall()
        resultado: dict[str, dict[str, int]] = {}
        for perfil, evento, count in linhas:
            resultado.setdefault(perfil, {})[evento] = count
        return resultado

    def historico_alertas(
        self, perfil: str | None = None, limite: int = 100
    ) -> list[dict[str, Any]]:
        if perfil:
            linhas = self._con.execute(
                "SELECT controle, visto_em, semana, objeto, valor, regra FROM vistos "
                "WHERE perfil = ? AND alertado = 1 ORDER BY visto_em DESC LIMIT ?",
                (perfil, limite),
            ).fetchall()
        else:
            linhas = self._con.execute(
                "SELECT controle, visto_em, semana, objeto, valor, regra, perfil FROM vistos "
                "WHERE alertado = 1 ORDER BY visto_em DESC LIMIT ?",
                (limite,),
            ).fetchall()
        return [
            {
                "controle": row[0],
                "visto_em": row[1],
                "semana": row[2],
                "objeto": row[3],
                "valor": row[4],
                "regra": row[5],
                **({"perfil": row[6]} if len(row) > 6 else {}),
            }
            for row in linhas
        ]

    def resumo_semanal(self, perfil: str | None = None) -> list[dict[str, Any]]:
        semana = datetime.now().strftime("%G-W%V")
        if perfil:
            linhas = self._con.execute(
                "SELECT controle, objeto, valor, regra FROM vistos "
                "WHERE perfil = ? AND semana = ? AND alertado = 1 "
                "ORDER BY COALESCE(valor, 0) DESC",
                (perfil, semana),
            ).fetchall()
        else:
            linhas = self._con.execute(
                "SELECT controle, objeto, valor, regra, perfil FROM vistos "
                "WHERE semana = ? AND alertado = 1 "
                "ORDER BY COALESCE(valor, 0) DESC",
                (semana,),
            ).fetchall()
        return [
            {"controle": row[0], "objeto": row[1], "valor": row[2], "regra": row[3],
             **({"perfil": row[4]} if len(row) > 4 else {})}
            for row in linhas
        ]

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
