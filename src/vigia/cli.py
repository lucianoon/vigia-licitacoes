from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import UTC, datetime
from typing import Any

from vigia import llm, matcher, notify
from vigia.cache import CachePncp
from vigia.config import Config, Perfil
from vigia.matcher import ResultadoRegra
from vigia.portal import Publicacao
from vigia.store import Store

logger = logging.getLogger(__name__)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


def _configurar_logging() -> None:
    nivel = os.environ.get("VIGIA_LOG_LEVEL", "INFO").upper()
    formato = os.environ.get("VIGIA_LOG_FORMAT", "text")

    if formato == "json":
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(JsonFormatter())
    else:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )

    logging.basicConfig(level=getattr(logging, nivel, logging.INFO), handlers=[handler])
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


async def _verificar_ou_avisar(config: Config) -> bool:
    """Verifica saúde dos portais. Retorna True se OK."""
    from vigia import registry

    nomes_portais = config.portais or ["pncp"]
    portais = registry.criar_portais(nomes_portais)

    todos_ok = True
    for portal in portais:
        if hasattr(portal, "verificar_saude"):
            ok = await portal.verificar_saude()
            if not ok:
                logger.warning("Portal %s esta indisponivel", portal.nome)
                print(f"  Aviso: {portal.nome} esta indisponivel.", file=sys.stderr)
                todos_ok = False
    return todos_ok


def _backup_automatico(store: Store) -> str | None:
    """Gera backup CSV antes de rodar. Retorna caminho ou None."""
    total = store.total()
    if total == 0:
        return None

    from vigia.exporter import exportar_csv

    try:
        agora = datetime.now().strftime("%Y-%m-%d_%H%M")
        backup_dir = os.environ.get(
            "VIGIA_BACKUP_DIR", os.path.join(os.getcwd(), "backups")
        )
        os.makedirs(backup_dir, exist_ok=True)
        caminho = os.path.join(backup_dir, f"backup_{agora}.csv")
        resultado = exportar_csv(store, caminho_saida=caminho)
        manter = max(int(os.environ.get("VIGIA_BACKUP_KEEP", "30")), 1)
        antigos = sorted(
            (
                entrada
                for entrada in os.scandir(backup_dir)
                if entrada.is_file()
                and entrada.name.startswith("backup_")
                and entrada.name.endswith(".csv")
            ),
            key=lambda entrada: entrada.name,
            reverse=True,
        )
        for entrada in antigos[manter:]:
            os.unlink(entrada.path)
        return resultado
    except Exception as exc:
        logger.warning("Backup falhou: %r", exc)
        return None


async def _buscar_portais(
    config: Config, dias: int, cache: CachePncp | None = None
) -> list[Publicacao]:
    """Busca publicações em todos os portais configurados."""
    from vigia import registry
    from vigia.pncp import janela_padrao

    todas_modalidades: set[int] = set()
    for perfil in config.perfis_resolvidos():
        todas_modalidades.update(perfil.filtros_globais.modalidades)
    todas_modalidades.update(config.filtros_globais.modalidades)

    inicio, fim = janela_padrao(dias=dias)
    nomes_portais = config.portais or ["pncp"]
    portais = registry.criar_portais(nomes_portais, cache=cache)

    todas: list[Publicacao] = []
    for portal in portais:
        print(f"Consultando {portal.nome} ({inicio} a {fim})...")
        try:
            publicacoes = await portal.buscar(
                inicio, fim, sorted(todas_modalidades)
            )
            print(f"  {len(publicacoes)} publicacoes de {portal.nome}.")
            todas.extend(publicacoes)
        except Exception as exc:
            logger.warning("Portal %s falhou: %r (continuando)", portal.nome, exc)
            print(
                f"  Aviso: {portal.nome} falhou ({exc}), "
                f"continuando com outros portais."
            )

    # Alguns agregadores republicam registros do PNCP com o mesmo controle.
    # Mantemos apenas a primeira ocorrência para não gerar alertas duplicados.
    unicas: dict[str, Publicacao] = {}
    sem_controle: list[Publicacao] = []
    for publicacao in todas:
        if publicacao.controle:
            unicas.setdefault(publicacao.controle, publicacao)
        else:
            sem_controle.append(publicacao)
    return [*unicas.values(), *sem_controle]


def _dias_restantes(item: dict[str, Any] | Publicacao) -> int:
    if isinstance(item, Publicacao):
        prazo = item.data_encerramento
    else:
        prazo = item.get("dataEncerramentoProposta")
    if not prazo:
        return 9999
    try:
        momento = datetime.fromisoformat(str(prazo))
    except ValueError:
        return 9999
    agora = datetime.now(momento.tzinfo) if momento.tzinfo else datetime.now()
    restantes = (momento - agora).days
    return max(restantes, -1)


def _para_dict(item: Publicacao) -> dict[str, Any]:
    """Converte Publicacao para dict (backward compatible com matcher)."""
    return {
        "numeroControlePNCP": item.controle,
        "objetoCompra": item.objeto,
        "orgaoEntidade": {"razaoSocial": item.orgao},
        "unidadeOrgao": {"uf": item.uf},
        "modalidadeNome": item.modalidade,
        "valorTotalEstimado": item.valor,
        "dataEncerramentoProposta": item.data_encerramento,
        "_portal": item.portal,
        "_url": item.url,
        **item.dados_raw,
    }


def _processar_perfil(
    perfil: Perfil,
    publicacoes: list[Publicacao],
    store: Store,
    seco: bool,
) -> list[tuple[Publicacao, ResultadoRegra, bool]]:
    novos: list[tuple[Publicacao, ResultadoRegra, bool]] = []
    lembretes: list[tuple[Publicacao, ResultadoRegra, bool]] = []

    for item in publicacoes:
        item_dict = _para_dict(item)
        resultados = matcher.avaliar(
            item_dict, perfil.filtros_globais, perfil.regras
        )
        if not resultados or not item.controle:
            continue

        if seco or store.nao_vistos([item.controle], perfil=perfil.nome):
            novos.append((item, resultados[0], False))
        elif _dias_restantes(item) <= 2 and store.pode_lembrar(
            item.controle, perfil=perfil.nome
        ):
            lembretes.append((item, resultados[0], True))

    novos.sort(key=lambda par: _dias_restantes(par[0]))
    lembretes.sort(key=lambda par: _dias_restantes(par[0]))
    return novos + lembretes


async def _enviar_notificacoes(
    perfil: Perfil,
    mensagens: list[str],
    controles: list[str],
    token: str,
    canal: str | None = None,
) -> set[str]:
    """Envia cada alerta e retorna os controles entregues em ao menos um canal."""
    entregues: set[str] = set()
    usar_whatsapp = canal in (None, "all", "whatsapp")
    usar_telegram = canal in (None, "all", "telegram")
    token_wa = os.environ.get("WHATSAPP_API_TOKEN", "")
    api_url = perfil.whatsapp.api_url or os.environ.get("WHATSAPP_API_URL", "")

    for mensagem, controle in zip(mensagens, controles, strict=True):
        entregue = False
        if usar_whatsapp and perfil.whatsapp.chat_id and token_wa and api_url:
            try:
                from vigia import whatsapp

                entregue = await whatsapp.enviar(
                    api_url, token_wa, perfil.whatsapp.chat_id, [mensagem]
                ) == 1
            except Exception as exc:
                logger.warning(
                    "WhatsApp falhou para %s (%s): %r", perfil.nome, controle, exc
                )

        if usar_telegram and token and perfil.chat_id:
            try:
                entregue = (
                    await notify.enviar(token, perfil.chat_id, [mensagem]) == 1
                    or entregue
                )
            except Exception as exc:
                logger.warning(
                    "Telegram falhou para %s (%s): %r", perfil.nome, controle, exc
                )

        if entregue:
            entregues.add(controle)

    return entregues


async def _rodar(
    caminho: str | None,
    dias: int,
    seco: bool = False,
    nome_perfil: str | None = None,
    canal: str | None = None,
    sem_backup: bool = False,
    sem_health_check: bool = False,
    portal: str | None = None,
) -> None:
    config = _carregar_config(caminho)
    if portal:
        config.portais = [portal]

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

    precisa_telegram = canal in (None, "all", "telegram") and any(
        perfil.chat_id for perfil in perfis
    )
    token = _token_telegram() if not seco and precisa_telegram else ""
    store = Store()
    cache = CachePncp()

    # Backup automático
    if not sem_backup and not seco:
        backup = _backup_automatico(store)
        if backup:
            print(f"Backup: {backup}")

    # Health check
    if not sem_health_check:
        print("Verificando portais...")
        ok = await _verificar_ou_avisar(config)
        if not ok:
            print("  Alguns portais estao indisponiveis. Continuando...", file=sys.stderr)

    t0 = time.monotonic()
    publicacoes = await _buscar_portais(config, dias, cache)
    tempo_busca = time.monotonic() - t0

    async def _processar_e_enviar(perfil: Perfil) -> tuple[int, int]:
        """Processa um perfil e retorna (total, enviadas)."""
        novos = _processar_perfil(perfil, publicacoes, store, seco)
        if not novos:
            print(f"\n--- Perfil: {perfil.nome} (0 novas oportunidades) ---")
            return 0, 0

        print(
            f"\n--- Perfil: {perfil.nome} "
            f"({len(novos)} novas oportunidades) ---"
        )

        mensagens: list[str] = []
        controles: list[str] = []
        eh_lembrete: list[bool] = []
        metadados: list[dict[str, Any]] = []
        for item, resultado, lembrete in novos:
            item_dict = _para_dict(item)
            resumo = await llm.resumir(item_dict)
            mensagens.append(
                notify.formatar_alerta(item_dict, resultado, resumo)
            )
            controles.append(item.controle)
            eh_lembrete.append(lembrete)
            metadados.append({
                "objeto": item.objeto[:200],
                "valor": item.valor,
                "regra": resultado.regra,
                "portal": item.portal,
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
            return len(novos), 0

        entregues = await _enviar_notificacoes(
            perfil, mensagens, controles, token, canal
        )
        controles_entregues = [c for c in controles if c in entregues]
        metadados_entregues = [
            meta for c, meta in zip(controles, metadados, strict=True) if c in entregues
        ]
        if controles_entregues:
            store.marcar_alertados(
                controles_entregues,
                perfil=perfil.nome,
                metadados=metadados_entregues,
            )
        enviadas = len(controles_entregues)
        store.registrar_metrica(
            perfil.nome, "alertas_enviados", str(enviadas)
        )
        print(f"  {enviadas} alerta(s) enviado(s).")
        return len(novos), enviadas

    # Processamento paralelo dos perfis
    resultados = await asyncio.gather(
        *[_processar_e_enviar(p) for p in perfis],
        return_exceptions=True,
    )

    total_geral = 0
    total_enviadas = 0
    for i, resultado in enumerate(resultados):
        if isinstance(resultado, BaseException):
            logger.error("Perfil %s falhou: %r", perfis[i].nome, resultado)
            print(
                f"\n--- Perfil: {perfis[i].nome} --- ERRO: {resultado}"
            )
            continue
        t, e = resultado
        total_geral += t
        total_enviadas += e

    cache.limpar_expirados()

    portais_usados = config.portais or ["pncp"]
    if seco:
        print(
            f"\nDry-run concluido: {total_geral} oportunidade(s) "
            f"NAO enviada(s)."
        )
    else:
        print(
            f"\nTotal: {total_geral} oportunidade(s), "
            f"{total_enviadas} alerta(s) enviados."
        )
    print(
        f"Portais: {', '.join(portais_usados)} | "
        f"Tempo: {tempo_busca:.1f}s | Cache: {cache.total()}"
    )
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
                print(
                    f"  [{perfil.nome}] {resultado.regra} "
                    f"(score {resultado.score})"
                )
                print(f"    casou: {', '.join(resultado.termos_casados)}")
                if resultado.destaques:
                    print(
                        f"    destaques: {', '.join(resultado.destaques)}"
                    )
        if not achou_perfil:
            print(f"  [{perfil.nome}] nenhuma regra casou.")

    if not achou:
        print(
            "\nNenhuma regra casou com o texto informado em nenhum perfil."
        )


def _gerar_digest(
    caminho: str | None, nome_perfil: str | None, enviar: bool
) -> None:
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
        itens: list[dict[str, Any]] = store.resumo_semanal(
            perfil=perfil.nome
        )
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
            asyncio.run(notify.enviar(token, perfil.chat_id, [digest]))
            print("  Digest enviado para o Telegram.")

    store.fechar()


def _exportar(
    caminho: str | None,
    formato: str,
    perfil_nome: str | None,
    desde: str | None,
    ate: str | None,
) -> None:
    from vigia.exporter import exportar_csv, exportar_xlsx

    store = Store()
    config = _carregar_config(caminho)
    perfis = [p.nome for p in config.perfis_resolvidos()]

    if perfil_nome and perfil_nome not in perfis:
        print(
            f"Erro: perfil '{perfil_nome}' nao encontrado. "
            f"Disponiveis: {', '.join(perfis)}",
            file=sys.stderr,
        )
        sys.exit(2)

    if formato == "csv":
        caminho_csv = exportar_csv(store, perfil_nome, desde, ate)
        print(f"CSV exportado: {caminho_csv}")
        print(f"Abra no Finder: open {os.path.abspath(caminho_csv)}")
    elif formato == "xlsx":
        caminho_xlsx = exportar_xlsx(store, perfil_nome, desde, ate)
        print(f"XLSX exportado: {caminho_xlsx}")
        print(f"Abra no Finder: open {os.path.abspath(caminho_xlsx)}")
    else:
        print(
            f"Formato nao suportado: {formato}. Use: csv ou xlsx",
            file=sys.stderr,
        )
        sys.exit(2)

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
        "--dias", type=int, default=2,
        help="Janela de dias do PNCP (padrao 2)",
    )
    rodar_parser.add_argument(
        "--dry-run", action="store_true",
        help="Mostra os alertas sem enviar nem marcar como vistos",
    )
    rodar_parser.add_argument(
        "--perfil",
        help="Executa apenas um perfil especifico (pelo nome)",
    )
    rodar_parser.add_argument(
        "--portal",
        choices=["pncp", "comprasnet"],
        help="Consulta apenas um portal (pncp, comprasnet)",
    )
    rodar_parser.add_argument(
        "--canal", choices=["telegram", "whatsapp", "all"],
        help="Canal de notificacao (padrao: todos configurados)",
    )
    rodar_parser.add_argument(
        "--sem-backup", action="store_true",
        help="Desabilita backup automatico antes de rodar",
    )
    rodar_parser.add_argument(
        "--sem-health-check", action="store_true",
        help="Desabilita verificacao de saude dos portais",
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
        "--perfil",
        help="Gera digest apenas para um perfil especifico",
    )
    digest_parser.add_argument(
        "--enviar", action="store_true",
        help="Envia o digest para o Telegram",
    )

    export_parser = subparsers.add_parser(
        "export",
        help="Exporta historico de alertas para CSV ou XLSX",
    )
    export_parser.add_argument("--config", help="Caminho do vigia.yaml")
    export_parser.add_argument(
        "--formato", choices=["csv", "xlsx"], default="csv",
        help="Formato de exportacao (padrao: csv)",
    )
    export_parser.add_argument(
        "--perfil",
        help="Exporta apenas um perfil especifico",
    )
    export_parser.add_argument(
        "--desde", help="Data inicial (YYYY-MM-DD)"
    )
    export_parser.add_argument(
        "--ate", help="Data final (YYYY-MM-DD)"
    )

    dashboard_parser = subparsers.add_parser(
        "dashboard",
        help="Gera dashboard HTML com historico e metricas",
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
                getattr(argumentos, "canal", None),
                getattr(argumentos, "sem_backup", False),
                getattr(argumentos, "sem_health_check", False),
                getattr(argumentos, "portal", None),
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
    elif argumentos.comando == "export":
        _exportar(
            argumentos.config,
            argumentos.formato,
            getattr(argumentos, "perfil", None),
            getattr(argumentos, "desde", None),
            getattr(argumentos, "ate", None),
        )
    elif argumentos.comando == "dashboard":
        _gerar_dashboard(argumentos.config)


if __name__ == "__main__":
    main()
