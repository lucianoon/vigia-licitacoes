from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time
from datetime import datetime
from typing import Any

from vigia import llm, matcher, notify, pncp
from vigia.cache import CachePncp
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
            "Erro: variavel de ambiente TELEGRAM_TOKEN nao definida.\n\n"
            "Para configurar:\n"
            "  1. Abra o Telegram e fale com @BotFather\n"
            "  2. Envie /newbot e copie o token\n"
            "  3. export TELEGRAM_TOKEN=\"SEU_TOKEN_AQUI\"\n\n"
            "Depois volte e execute novamente.",
            file=sys.stderr,
        )
        sys.exit(2)
    return token


def _carregar_config(caminho: str | None) -> Config:
    try:
        return Config.carregar(caminho)
    except FileNotFoundError as exc:
        print(
            f"Erro: {exc}\n\n"
            "Para criar a configuracao:\n"
            "  cp vigia.example.yaml vigia.yaml\n"
            "  vim vigia.yaml  # edite regras, chat_id, segmento",
            file=sys.stderr,
        )
        sys.exit(2)
    except ValueError as exc:
        print(f"Erro na configuracao: {exc}", file=sys.stderr)
        sys.exit(2)


async def _fetch_publicacoes(
    config: Config, dias: int, cache: CachePncp | None = None
) -> list[dict[str, Any]]:
    todas_modalidades: set[int] = set()
    for perfil in config.perfis_resolvidos():
        todas_modalidades.update(perfil.filtros_globais.modalidades)
    todas_modalidades.update(config.filtros_globais.modalidades)

    inicio, fim = pncp.janela_padrao(dias=dias)
    print(f"Consultando PNCP ({inicio} a {fim})...")
    try:
        publicacoes = await pncp.buscar_publicacoes(
            inicio, fim, sorted(todas_modalidades), cache=cache
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
    caminho: str | None,
    dias: int,
    seco: bool = False,
    nome_perfil: str | None = None,
) -> None:
    config = _carregar_config(caminho)
    token = "" if seco else _token_telegram()
    store = Store()
    cache = CachePncp()

    t0 = time.monotonic()
    publicacoes = await _fetch_publicacoes(config, dias, cache)
    tempo_pncp = time.monotonic() - t0

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
        metadados: list[dict[str, Any]] = []
        for item, resultado in novos:
            resumo = await llm.resumir(item)
            mensagens.append(notify.formatar_alerta(item, resultado, resumo))
            controles.append(str(item.get("numeroControlePNCP")))
            eh_lembrete.append(_dias_restantes(item) <= 2)
            metadados.append({
                "objeto": str(item.get("objetoCompra", ""))[:200],
                "valor": item.get("valorTotalEstimado"),
                "regra": resultado.regra,
            })

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
        store.marcar_alertados(controles, perfil=perfil.nome, metadados=metadados)
        store.registrar_metrica(perfil.nome, "alertas_enviados", str(enviadas))
        total_enviadas += enviadas
        print(f"  {enviadas} alerta(s) enviado(s) para o Telegram.")

    cache.limpar_expirados()

    if seco:
        print(f"\nDry-run concluido: {total_geral} oportunidade(s) NAO enviada(s).")
    else:
        print(f"\nTotal: {total_geral} oportunidade(s), {total_enviadas} alerta(s) enviados.")
    print(f"Tempo PNCP: {tempo_pncp:.1f}s | Cache: {cache.total()} entradas")
    store.fechar()
    cache.fechar()


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


def _gerar_digest(caminho: str | None, nome_perfil: str | None, enviar: bool) -> None:
    config = _carregar_config(caminho)
    store = Store()

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

    token = _token_telegram() if enviar else ""

    for perfil in perfis:
        itens: list[dict[str, Any]] = store.resumo_semanal(perfil=perfil.nome)
        if not itens:
            print(f"\n--- {perfil.nome}: nada esta semana ---")
            continue

        total = len(itens)
        valor_total = sum(i.get("valor") or 0 for i in itens)
        valor_txt = (
            f"R$ {valor_total:,.0f}".replace(",", ".")
            if valor_total
            else "valor nao informado"
        )
        regras: dict[str, int] = {}
        for item_semanal in itens:
            r = item_semanal.get("regra", "?")
            regras[r] = regras.get(r, 0) + 1

        linhas = [
            f"Digest semanal - {perfil.nome}",
            f"Semana {datetime.now().strftime('%G-W%V')}",
            "",
            f"{total} oportunidade(s) encontrada(s)",
            f"Valor total estimado: {valor_txt}",
            "",
            "Por regra:",
        ]
        for regra, count in sorted(regras.items(), key=lambda x: -x[1]):
            linhas.append(f"  - {regra}: {count}")

        top = [i for i in itens if i.get("valor")][:5]
        if top:
            linhas.append("")
            linhas.append("Top 5 por valor:")
            for i, item in enumerate(top, 1):
                val = item.get("valor") or 0
                val_txt = f"R$ {val:,.0f}".replace(",", ".")
                obj = (item.get("objeto") or "")[:80]
                linhas.append(f"  {i}. {val_txt} - {obj}")

        linhas.append("")
        linhas.append("https://pncp.gov.br/app/editais")

        digest = "\n".join(linhas)
        print(f"\n{'=' * 50}")
        print(digest)
        print(f"{'=' * 50}")

        if enviar and token:
            asyncio.run(
                notify.enviar(token, perfil.telegram.chat_id, [digest])
            )
            print("  Digest enviado para o Telegram.")

    store.fechar()


def _gerar_dashboard(caminho: str | None) -> None:
    from vigia.dashboard import gerar_dashboard_html

    store = Store()
    config = _carregar_config(caminho)
    perfis = [p.nome for p in config.perfis_resolvidos()]
    caminho_html = gerar_dashboard_html(store, perfis)
    store.fechar()
    print(f"Dashboard gerado: {caminho_html}")
    print(f"Abra no navegador: file://{os.path.abspath(caminho_html)}")


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

    digest_parser = subparsers.add_parser(
        "digest", help="Gera o digest semanal de licitacoes"
    )
    digest_parser.add_argument("--config", help="Caminho do vigia.yaml")
    digest_parser.add_argument(
        "--perfil", help="Gera digest apenas para um perfil especifico"
    )
    digest_parser.add_argument(
        "--enviar",
        action="store_true",
        help="Envia o digest para o Telegram",
    )

    dashboard_parser = subparsers.add_parser(
        "dashboard", help="Gera dashboard HTML com historico e metricas"
    )
    dashboard_parser.add_argument("--config", help="Caminho do vigia.yaml")

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
    elif argumentos.comando == "digest":
        _gerar_digest(
            argumentos.config,
            getattr(argumentos, "perfil", None),
            argumentos.enviar,
        )
    elif argumentos.comando == "dashboard":
        _gerar_dashboard(argumentos.config)


if __name__ == "__main__":
    main()
