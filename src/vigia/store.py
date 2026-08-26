from __future__ import annotations

import os
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
    portal TEXT NOT NULL DEFAULT '',
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
    def __init__(self, caminho: str | None = None) -> None:
        self.caminho = Path(caminho or os.environ.get("VIGIA_DB_PATH", "vigia.db"))
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self._con = self._conectar()

    def _conectar(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.caminho)
        con.execute(SCHEMA_VISTOS)
        con.execute(SCHEMA_METRICAS)
        self._migrar_vistos(con)
        con.commit()
        return con

    @staticmethod
    def _migrar_vistos(con: sqlite3.Connection) -> None:
        """Atualiza schemas antigos preservando o histórico existente."""
        info = con.execute("PRAGMA table_info(vistos)").fetchall()
        colunas = {str(linha[1]) for linha in info}
        pk = [str(linha[1]) for linha in sorted(info, key=lambda linha: linha[5]) if linha[5]]
        esperadas = {
            "controle", "perfil", "visto_em", "alertado", "semana",
            "objeto", "valor", "regra", "portal",
        }
        if esperadas.issubset(colunas) and pk == ["controle", "perfil"]:
            return

        expressoes = {
            "controle": "controle",
            "perfil": "COALESCE(perfil, '__global__')" if "perfil" in colunas else "'__global__'",
            "visto_em": "visto_em" if "visto_em" in colunas else "datetime('now')",
            "alertado": "alertado" if "alertado" in colunas else "1",
            "semana": "semana" if "semana" in colunas else "''",
            "objeto": "objeto" if "objeto" in colunas else "''",
            "valor": "valor" if "valor" in colunas else "NULL",
            "regra": "regra" if "regra" in colunas else "''",
            "portal": "portal" if "portal" in colunas else "''",
        }
        destino = list(expressoes)
        con.execute("ALTER TABLE vistos RENAME TO vistos_legacy")
        con.execute(SCHEMA_VISTOS)
        con.execute(
            f"INSERT OR REPLACE INTO vistos ({', '.join(destino)}) "
            f"SELECT {', '.join(expressoes[c] for c in destino)} FROM vistos_legacy"
        )
        con.execute("DROP TABLE vistos_legacy")

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
                meta.get("portal", ""),
            ))
        self._con.executemany(
            "INSERT INTO vistos "
            "(controle, perfil, visto_em, alertado, semana, objeto, valor, regra, portal) "
            "VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?) "
            "ON CONFLICT(controle, perfil) DO UPDATE SET "
            "visto_em = ?, alertado = 1, semana = ?, objeto = ?, valor = ?, regra = ?, portal = ?",
            [
                (*row, row[2], row[3], row[4], row[5], row[6], row[7])
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
        quantidade = (
            "SUM(CASE WHEN evento = 'alertas_enviados' "
            "THEN CAST(detalhe AS INTEGER) ELSE 1 END)"
        )
        if perfil:
            linhas = self._con.execute(
                f"SELECT evento, {quantidade} FROM metricas "
                "WHERE perfil = ? AND criado_em >= ? GROUP BY evento",
                (perfil, desde),
            ).fetchall()
        else:
            linhas = self._con.execute(
                f"SELECT evento, {quantidade} FROM metricas "
                "WHERE criado_em >= ? GROUP BY evento",
                (desde,),
            ).fetchall()
        return {row[0]: row[1] for row in linhas}

    def metricas_por_perfil(self, dias: int = 30) -> dict[str, dict[str, int]]:
        desde = (datetime.now() - timedelta(days=dias)).isoformat(timespec="seconds")
        linhas = self._con.execute(
            "SELECT perfil, evento, "
            "SUM(CASE WHEN evento = 'alertas_enviados' "
            "THEN CAST(detalhe AS INTEGER) ELSE 1 END) FROM metricas "
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
                "SELECT controle, visto_em, semana, objeto, valor, regra, portal "
                "FROM vistos WHERE perfil = ? AND alertado = 1 "
                "ORDER BY visto_em DESC LIMIT ?",
                (perfil, limite),
            ).fetchall()
        else:
            linhas = self._con.execute(
                "SELECT controle, visto_em, semana, objeto, valor, regra, perfil, portal "
                "FROM vistos WHERE alertado = 1 "
                "ORDER BY visto_em DESC LIMIT ?",
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
                "portal": row[7] if len(row) > 7 else row[6] if len(row) > 6 else "",
                **({"perfil": row[6]} if len(row) > 7 else {}),
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
