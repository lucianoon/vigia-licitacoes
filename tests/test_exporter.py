from __future__ import annotations

import csv
import os
from pathlib import Path

import pytest

from vigia.exporter import exportar_csv
from vigia.store import Store


def _popular_store(store: Store) -> None:
    meta = [
        {"objeto": "Manutencao ar", "valor": 50000, "regra": "Climatizacao", "portal": "pncp"},
        {"objeto": "Chiller", "valor": 120000, "regra": "Climatizacao", "portal": "pncp"},
        {"objeto": "Papel", "valor": 3000, "regra": "Escritorio", "portal": "comprasnet"},
    ]
    store.marcar_alertados(
        ["PE001", "PE002", "PE003"], perfil="clima", metadados=meta,
    )


def test_exportar_csv(tmp_path: Path) -> None:
    store = Store(str(tmp_path / "test.db"))
    _popular_store(store)

    os.chdir(tmp_path)
    caminho = exportar_csv(store)
    assert Path(caminho).exists()

    with open(caminho, encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)

    assert len(rows) == 3
    assert rows[0]["objeto"] == "Manutencao ar"
    assert rows[0]["regra"] == "Climatizacao"
    store.fechar()


def test_exportar_csv_filtro_perfil(tmp_path: Path) -> None:
    store = Store(str(tmp_path / "test.db"))
    _popular_store(store)

    os.chdir(tmp_path)
    caminho = exportar_csv(store, perfil="clima")
    with open(caminho, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    assert len(rows) == 3
    store.fechar()


def test_exportar_csv_filtro_data(tmp_path: Path) -> None:
    store = Store(str(tmp_path / "test.db"))
    _popular_store(store)

    from datetime import datetime

    os.chdir(tmp_path)
    hoje = datetime.now().strftime("%Y-%m-%d")
    caminho = exportar_csv(store, desde=hoje, ate=hoje)
    with open(caminho, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    assert len(rows) == 3
    store.fechar()


def test_exportar_csv_vazio(tmp_path: Path) -> None:
    store = Store(str(tmp_path / "test.db"))
    os.chdir(tmp_path)
    caminho = exportar_csv(store)
    with open(caminho, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 0
    store.fechar()


try:
    from openpyxl import load_workbook  # type: ignore[import-untyped]

    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False


@pytest.mark.skipif(not HAS_OPENPYXL, reason="openpyxl nao instalado")
def test_exportar_xlsx(tmp_path: Path) -> None:
    from vigia.exporter import exportar_xlsx

    store = Store(str(tmp_path / "test.db"))
    _popular_store(store)

    os.chdir(tmp_path)
    caminho = exportar_xlsx(store, perfil="clima")
    assert Path(caminho).exists()
    assert caminho.endswith(".xlsx")

    wb = load_workbook(caminho)
    ws = wb.active
    assert ws.title == "Alertas"
    assert ws.cell(row=1, column=1).value == "Data"
    assert ws.cell(row=2, column=3).value == "Manutencao ar-condicionado"
    store.fechar()


@pytest.mark.skipif(not HAS_OPENPYXL, reason="openpyxl nao instalado")
def test_exportar_xlsx_vazio(tmp_path: Path) -> None:
    from vigia.exporter import exportar_xlsx

    store = Store(str(tmp_path / "test.db"))
    os.chdir(tmp_path)
    caminho = exportar_xlsx(store)
    assert Path(caminho).exists()

    wb = load_workbook(caminho)
    ws = wb.active
    assert ws.max_row == 1
    store.fechar()
