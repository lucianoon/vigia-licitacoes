from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime
from typing import Any

from vigia import llm, matcher, notify, pncp
from vigia.config import Config, Perfil
from vigia.matcher import ResultadoRegra
from vigia.store import Store


def _configurar_logging() -> None:
    nivel = os.environ.get("VIGIA_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, nivel, logging.INFO),
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)


def _token_telegram() -> str:
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        print(
            "Erro: variavel de ambiente TELEGRAM_TOKEN nao definida.\n"
            "Crie um bot com @BotFather no Telegram e exporte o token.",
            file=sys.stderr,
        )
        sys.exit(2)
    return token


def _carregar_config(caminho: str | None) -> Config:
    try:
        return Config.carregar(caminho)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        sys.exit(2)


async def _fetch_publicacoes(
    config: Config, dias: int
) -> list[dict[str, Any]]:
    todas_modalidades: set[int] = set()
    for perfil in config.perfis_resolvidos():
        todas_modalidades.update(perfil.filtros_globais.modalidades)
    todas_modalidades.update(config.filtros_globais.modalidades)

    inicio, fim = pncp.janela_padrao(dias=dias)
    print(f"Consultando PNCP ({inicio} a {fim})...")
    try:
        publicacoes = await pncp.buscar_publicacoes(
            inicio, fim, sorted(todas_modalidades)
        )
    except pncp.PncpError as exc:
        print(f"Erro ao consultar o PNCP: {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"{len(publicacoes)} publicacoes recebidas.")
    return publicacoes


def _dias_restantes(item: dict[str, Any]) -> int:
    prazo = item.get("dataEncerramentoProposta")
    if not prazo:
        return 9999
    try:
        momento = datetime.fromisoformat(str(prazo))
    except ValueError:
        return 9999
    restantes = (momento - datetime.now()).days
    return max(restantes, -1)


def _processar_perfil(
    perfil: Perfil,
    publicacoes: list[dict[str, Any]],
    store: Store,
    seco: bool,
    token: str,
) -> list[tuple[dict[str, Any], ResultadoRegra]]:
    novos: list[tuple[dict[str, Any], ResultadoRegra]] = []
    lembretes: list[tuple[dict[str, Any], ResultadoRegra]] = []

    for item in publicacoes:
        controle = str(item.get("numeroControlePNCP") or "")
        resultados = matcher.avaliar(
            item, perfil.filtros_globais, perfil.regras
        )
        if not resultados or not controle:
            continue

        if seco or store.nao_vistos([controle], perfil=perfil.nome):
            novos.append((item, resultados[0]))
        elif _dias_restantes(item) <= 2 and store.pode_lembrar(controle):
            lembretes.append((item, resultados[0]))

    novos.sort(key=lambda par: _dias_restantes(par[0]))
    lembretes.sort(key=lambda par: _dias_restantes(par[0]))
    return novos + lembretes


async def _rodar(
    caminho: str | None, dias: int, seco: bool = False, nome_perfil: str | None = None
) -> None:
    config = _carregar_config(caminho)
    token = "" if seco else _token_telegram()
    store = Store()

    publicacoes = await _fetch_publicacoes(config, dias)

    perfis = config.perfis_resolvidos()
    if nome_perfil:
        perfis = [p for p in perfis if p.nome == nome_perfil]
        if not perfis:
            nomes = ", ".join(p.nome for p in config.perfis_resolvidos())
            print(
                f"Erro: perfil '{nome_perfil}' nao encontrado. "
                f"Disponiveis: {nomes}",
                file=sys.stderr,
            )
            sys.exit(2)

    total_geral = 0
    total_enviadas = 0

    for perfil in perfis:
        novos = _processar_perfil(perfil, publicacoes, store, seco, token)
        total_geral += len(novos)
        print(f"\n--- Perfil: {perfil.nome} ({len(novos)} novas oportunidades) ---")

        if not novos:
            print("  Nada novo para este perfil.")
            continue

        mensagens: list[str] = []
        controles: list[str] = []
        eh_lembrete: list[bool] = []
        for item, resultado in novos:
            resumo = await llm.resumir(item)
            mensagens.append(notify.formatar_alerta(item, resultado, resumo))
            controles.append(str(item.get("numeroControlePNCP")))
            eh_lembrete.append(_dias_restantes(item) <= 2)

        if seco:
            for indice, (mensagem, lembrete) in enumerate(
                zip(mensagens, eh_lembrete, strict=True), start=1
            ):
                tag = " [LEMBRETE]" if lembrete else ""
                print(
                    f"\n  [Dry-run] Alerta {indice}/{len(mensagens)}{tag}:"
                )
                print(f"  {mensagem}")
            continue

        enviadas = await notify.enviar(token, perfil.telegram.chat_id, mensagens)
        store.marcar_alertados(controles, perfil=perfil.nome)
        total_enviadas += enviadas
        print(f"  {enviadas} alerta(s) enviado(s) para o Telegram.")

    if seco:
        print(f"\nDry-run concluido: {total_geral} oportunidade(s) NAO enviada(s).")
    else:
        print(f"\nTotal: {total_geral} oportunidade(s), {total_enviadas} alerta(s) enviados.")
    store.fechar()


def _testar_regras(caminho: str | None, texto: str) -> None:
    config = _carregar_config(caminho)
    from vigia.matcher import avaliar_regra, normalizar

    objeto = normalizar(texto)
    achou = False

    for perfil in config.perfis_resolvidos():
        achou_perfil = False
        for regra in perfil.regras:
            resultado = avaliar_regra(objeto, regra)
            if resultado:
                achou = True
                achou_perfil = True
                print(f"  [{perfil.nome}] {resultado.regra} (score {resultado.score})")
                print(f"    casou: {', '.join(resultado.termos_casados)}")
                if resultado.destaques:
                    print(f"    destaques: {', '.join(resultado.destaques)}")
        if not achou_perfil:
            print(f"  [{perfil.nome}] nenhuma regra casou.")

    if not achou:
        print("\nNenhuma regra casou com o texto informado em nenhum perfil.")


def main() -> None:
    _configurar_logging()
    parser = argparse.ArgumentParser(
        prog="vigia", description="Monitor de licitacoes do PNCP"
    )
    subparsers = parser.add_subparsers(dest="comando", required=True)

    rodar_parser = subparsers.add_parser(
        "run", help="Executa um ciclo de monitoramento"
    )
    rodar_parser.add_argument("--config", help="Caminho do vigia.yaml")
    rodar_parser.add_argument(
        "--dias",
        type=int,
        default=2,
        help="Janela de dias do PNCP (padrao 2)",
    )
    rodar_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra os alertas sem enviar nem marcar como vistos",
    )
    rodar_parser.add_argument(
        "--perfil",
        help="Executa apenas um perfil especifico (pelo nome)",
    )

    testar_parser = subparsers.add_parser(
        "test-regras", help="Testa as regras contra um texto de objeto"
    )
    testar_parser.add_argument("texto")
    testar_parser.add_argument("--config", help="Caminho do vigia.yaml")

    argumentos = parser.parse_args()

    if argumentos.comando == "run":
        asyncio.run(
            _rodar(
                argumentos.config,
                argumentos.dias,
                argumentos.dry_run,
                getattr(argumentos, "perfil", None),
            )
        )
    elif argumentos.comando == "test-regras":
        _testar_regras(argumentos.config, argumentos.texto)


if __name__ == "__main__":
    main()
