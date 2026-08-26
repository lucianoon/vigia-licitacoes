from __future__ import annotations

import html
import os
from datetime import datetime
from typing import Any

from vigia.store import Store


def _esc(texto: str) -> str:
    return html.escape(str(texto))


def _fmt_valor(valor: float | None) -> str:
    if valor is None or valor == 0:
        return "-"
    return f"R$ {valor:,.0f}".replace(",", ".")


def _gerar_html(
    historico: list[dict[str, Any]],
    metricas: dict[str, Any],
    metricas_por_perfil: dict[str, dict[str, int]],
    total_itens: int,
    perfis: list[str],
) -> str:
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")

    # Metricas por perfil
    linhas_perfil = ""
    for perfil, metricas_p in metricas_por_perfil.items():
        enviados = metricas_p.get("alertas_enviados", 0)
        linhas_perfil += f"""
        <tr>
          <td>{_esc(perfil)}</td>
          <td>{enviados}</td>
        </tr>"""

    # Historico recente
    linhas_historico = ""
    for item in historico[:50]:
        valor = _fmt_valor(item.get("valor"))
        objeto = _esc((item.get("objeto") or "")[:100])
        regra = _esc(item.get("regra", ""))
        visto = _esc(item.get("visto_em", ""))
        perfil_item = _esc(item.get("perfil", ""))
        linhas_historico += f"""
        <tr>
          <td>{visto}</td>
          <td>{perfil_item}</td>
          <td title="{_esc(item.get('objeto', ''))}">{objeto}</td>
          <td>{regra}</td>
          <td class="valor">{valor}</td>
        </tr>"""

    # Metricas gerais
    linhas_metricas = ""
    for evento, count in sorted(metricas.items()):
        linhas_metricas += f"""
        <tr>
          <td>{_esc(evento)}</td>
          <td>{count}</td>
        </tr>"""

    # Grafico de atividade semanal (baseado no historico)
    semanas: dict[str, int] = {}
    for item in historico:
        s = item.get("semana", "")
        if s:
            semanas[s] = semanas.get(s, 0) + 1
    semanas_ordenadas = sorted(semanas.items())[-12:]
    max_count = max((c for _, c in semanas_ordenadas), default=1)

    barras = ""
    for semana, count in semanas_ordenadas:
        altura = int((count / max_count) * 150) if max_count > 0 else 0
        barras += f"""
        <div class="barra">
          <div class="barra-fill" style="height: {altura}px;"></div>
          <div class="barra-label">{semana[-5:]}</div>
          <div class="barra-valor">{count}</div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Vigia - Dashboard de Licitacoes</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #0f172a; color: #e2e8f0; padding: 24px; }}
  h1 {{ font-size: 1.8rem; margin-bottom: 4px; color: #38bdf8; }}
  .subtitle {{ color: #94a3b8; margin-bottom: 24px; font-size: 0.9rem; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
           gap: 16px; margin-bottom: 24px; }}
  .card {{ background: #1e293b; border-radius: 12px; padding: 20px; }}
  .card h3 {{ color: #94a3b8; font-size: 0.8rem; text-transform: uppercase;
              letter-spacing: 0.05em; margin-bottom: 8px; }}
  .card .num {{ font-size: 2rem; font-weight: 700; color: #38bdf8; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
  th {{ text-align: left; padding: 8px 12px; background: #1e293b; color: #94a3b8;
        font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em;
        border-bottom: 1px solid #334155; }}
  td {{ padding: 8px 12px; border-bottom: 1px solid #1e293b; font-size: 0.85rem; }}
  tr:hover td {{ background: #1e293b; }}
  .valor {{ font-family: 'SF Mono', monospace; text-align: right; white-space: nowrap; }}
  .chart {{ display: flex; align-items: flex-end; gap: 4px; height: 200px;
            padding: 16px 0; }}
  .barra {{ display: flex; flex-direction: column; align-items: center;
            flex: 1; min-width: 40px; }}
  .barra-fill {{ width: 100%; background: linear-gradient(180deg, #38bdf8, #0ea5e9);
                 border-radius: 4px 4px 0 0; min-height: 2px; transition: height 0.3s; }}
  .barra-label {{ font-size: 0.65rem; color: #64748b; margin-top: 4px;
                  writing-mode: vertical-rl; transform: rotate(180deg); max-height: 60px; }}
  .barra-valor {{ font-size: 0.7rem; color: #38bdf8; font-weight: 600; }}
  .section {{ margin-bottom: 24px; }}
  .section h2 {{ font-size: 1.1rem; margin-bottom: 12px; color: #e2e8f0; }}
</style>
</head>
<body>
  <h1>Vigia - Dashboard</h1>
  <p class="subtitle">Atualizado em {agora} | {total_itens} itens monitorados</p>

  <div class="grid">
    <div class="card">
      <h3>Total de alertas</h3>
      <div class="num">{total_itens}</div>
    </div>
    <div class="card">
      <h3>Perfis ativos</h3>
      <div class="num">{len(perfis)}</div>
    </div>
    <div class="card">
      <h3>Alertas enviados (30d)</h3>
      <div class="num">{sum(v for v in metricas.values())}</div>
    </div>
  </div>

  <div class="section">
    <h2>Atividade semanal</h2>
    <div class="card">
      <div class="chart">{barras}</div>
    </div>
  </div>

  <div class="section">
    <h2>Metricas por perfil</h2>
    <div class="card">
      <table>
        <thead><tr><th>Perfil</th><th>Alertas enviados</th></tr></thead>
        <tbody>{linhas_perfil or '<tr><td colspan="2">Nenhuma metrica ainda</td></tr>'}</tbody>
      </table>
    </div>
  </div>

  <div class="section">
    <h2>Top 10 por valor estimado</h2>
    <div class="card">
      <table>
        <thead><tr><th>Data</th><th>Perfil</th><th>Objeto</th><th>Regra</th><th>Valor</th></tr></thead>
        <tbody>{linhas_historico or '<tr><td colspan="5">Nenhum item ainda</td></tr>'}</tbody>
      </table>
    </div>
  </div>

  <div class="section">
    <h2>Metricas gerais (30 dias)</h2>
    <div class="card">
      <table>
        <thead><tr><th>Evento</th><th>Quantidade</th></tr></thead>
        <tbody>{linhas_metricas or '<tr><td colspan="2">Nenhuma metrica ainda</td></tr>'}</tbody>
      </table>
    </div>
  </div>

  <div class="section">
    <h2>Historico recente (ultimos 50)</h2>
    <div class="card">
      <table>
        <thead><tr><th>Data</th><th>Perfil</th><th>Portal</th><th>Objeto</th><th>Regra</th><th>Valor</th></tr></thead>
        <tbody>{linhas_historico or '<tr><td colspan="6">Nenhum item ainda</td></tr>'}</tbody>
      </table>
    </div>
  </div>
</body>
</html>"""


def gerar_dashboard_html(
    store: Store,
    perfis: list[str] | None = None,
    caminho_saida: str | None = None,
) -> str:
    historico = store.historico_alertas(limite=200)
    metricas = store.metricas(dias=30)
    metricas_por = store.metricas_por_perfil(dias=30)
    total = store.total()

    conteudo = _gerar_html(
        historico, metricas, metricas_por, total, perfis or []
    )

    if caminho_saida is None:
        caminho_saida = os.path.join(os.getcwd(), "dashboard.html")
    with open(caminho_saida, "w", encoding="utf-8") as fh:
        fh.write(conteudo)
    return caminho_saida
