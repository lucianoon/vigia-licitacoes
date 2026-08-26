import argparse
import asyncio
import logging
import os
import sys
from typing import Any

from vigia import llm, matcher, notify, pncp
from vigia.config import Config
from vigia.matcher import ResultadoRegra
from vigia.store import Store


def _configurar_logging() -> None:
    nivel = os.environ.get("VIGIA_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, nivel, logging.INFO),
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _token_telegram() -> str:
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        print(
            "Erro: variável de ambiente TELEGRAM_TOKEN não definida.\n"
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


async def _rodar(caminho: str | None, dias: int) -> None:
    config = _carregar_config(caminho)
    token = _token_telegram()
    store = Store()

    inicio, fim = pncp.janela_padrao(dias=dias)
    print(f"Consultando PNCP ({inicio} a {fim})...")
    try:
        publicacoes = await pncp.buscar_publicacoes(
            inicio, fim, config.filtros_globais.modalidades
        )
    except pncp.PncpError as exc:
        print(f"Erro ao consultar o PNCP: {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"{len(publicacoes)} publicações recebidas.")

    novos: list[tuple[dict[str, Any], ResultadoRegra]] = []
    for item in publicacoes:
        controle = str(item.get("numeroControlePNCP") or "")
        resultados = matcher.avaliar(item, config.filtros_globais, config.regras)
        if not resultados or not controle:
            continue
        if store.nao_vistos([controle]):
            melhores = resultados[0]
            novos.append((item, melhores))

    print(f"{len(novos)} novas oportunidades após filtros e regras.")
    if not novos:
        print("Nada novo. Vigia dormindo. 😴")
        return

    mensagens: list[str] = []
    controles: list[str] = []
    for item, resultado in novos:
        resumo = await llm.resumir(item)
        mensagens.append(notify.formatar_alerta(item, resultado, resumo))
        controles.append(str(item.get("numeroControlePNCP")))

    enviadas = await notify.enviar(token, config.telegram.chat_id, mensagens)
    store.marcar_alertados(controles)
    print(f"✅ {enviadas} alerta(s) enviado(s) para o Telegram.")
    store.fechar()


def _testar_regras(caminho: str | None, texto: str) -> None:
    config = _carregar_config(caminho)
    from vigia.matcher import avaliar_regra, normalizar

    objeto = normalizar(texto)
    achou = False
    for regra in config.regras:
        resultado = avaliar_regra(objeto, regra)
        if resultado:
            achou = True
            print(f"✅ {resultado.regra} (score {resultado.score})")
            print(f"   casou: {', '.join(resultado.termos_casados)}")
            if resultado.destaques:
                print(f"   destaques: {', '.join(resultado.destaques)}")
    if not achou:
        print("❌ Nenhuma regra casou com o texto informado.")


def main() -> None:
    _configurar_logging()
    parser = argparse.ArgumentParser(prog="vigia", description="Monitor de licitações do PNCP")
    subparsers = parser.add_subparsers(dest="comando", required=True)

    rodar_parser = subparsers.add_parser("run", help="Executa um ciclo de monitoramento")
    rodar_parser.add_argument("--config", help="Caminho do vigia.yaml")
    rodar_parser.add_argument(
        "--dias", type=int, default=2, help="Janela de dias do PNCP (padrão 2)"
    )

    testar_parser = subparsers.add_parser(
        "test-regras", help="Testa as regras contra um texto de objeto"
    )
    testar_parser.add_argument("texto")
    testar_parser.add_argument("--config", help="Caminho do vigia.yaml")

    argumentos = parser.parse_args()

    if argumentos.comando == "run":
        asyncio.run(_rodar(argumentos.config, argumentos.dias))
    elif argumentos.comando == "test-regras":
        _testar_regras(argumentos.config, argumentos.texto)


if __name__ == "__main__":
    main()
