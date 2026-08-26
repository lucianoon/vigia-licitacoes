from __future__ import annotations

import html
import json
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

    # Extract unique values for filters
    perfis_unicos = sorted({item.get("perfil", "") for item in historico if item.get("perfil")})
    portais_unicos = sorted({item.get("portal", "") for item in historico if item.get("portal")})
    datas = [item.get("visto_em", "")[:10] for item in historico if item.get("visto_em")]
    data_min = min(datas) if datas else ""
    data_max = max(datas) if datas else ""

    # Metricas por perfil
    linhas_perfil = ""
    for perfil, metricas_p in metricas_por_perfil.items():
        enviados = metricas_p.get("alertas_enviados", 0)
        linhas_perfil += f"""
        <tr>
          <td>{_esc(perfil)}</td>
          <td>{enviados}</td>
        </tr>"""

    # Historico rows as JSON for filtering
    historico_json = json.dumps(historico[:200], ensure_ascii=False, default=str)
    historico_json = (
        historico_json.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )

    # Metricas gerais
    linhas_metricas = ""
    for evento, count in sorted(metricas.items()):
        linhas_metricas += f"""
        <tr>
          <td>{_esc(evento)}</td>
          <td>{count}</td>
        </tr>"""

    # Grafico de atividade semanal
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

    # Build filter options HTML
    perfil_options = "".join(
        f'<option value="{_esc(p)}">{_esc(p)}</option>' for p in perfis_unicos
    )
    portal_options = "".join(
        f'<option value="{_esc(p)}">{_esc(p)}</option>' for p in portais_unicos
    )

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
        border-bottom: 1px solid #334155; position: sticky; top: 0; }}
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
  .filters {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }}
  .filters label {{ color: #94a3b8; font-size: 0.8rem; }}
  .filters select, .filters input {{ background: #0f172a; color: #e2e8f0;
    border: 1px solid #334155; border-radius: 6px; padding: 6px 10px; font-size: 0.85rem; }}
  .filters select:focus, .filters input:focus {{ outline: none; border-color: #38bdf8; }}
  .filters button {{ background: #38bdf8; color: #0f172a; border: none;
    border-radius: 6px; padding: 6px 14px; font-size: 0.85rem; cursor: pointer;
    font-weight: 600; }}
  .filters button:hover {{ background: #0ea5e9; }}
  .count-badge {{ background: #334155; color: #94a3b8; padding: 2px 8px;
    border-radius: 10px; font-size: 0.75rem; margin-left: 8px; }}
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
      <div class="num">{metricas.get('alertas_enviados', 0)}</div>
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
    <h2>Historico <span class="count-badge" id="count-badge">0</span></h2>
    <div class="card">
      <div class="filters">
        <div>
          <label>Perfil</label><br>
          <select id="filter-perfil"><option value="">Todos</option>{perfil_options}</select>
        </div>
        <div>
          <label>Portal</label><br>
          <select id="filter-portal"><option value="">Todos</option>{portal_options}</select>
        </div>
        <div>
          <label>De</label><br>
          <input type="date" id="filter-desde" value="{data_min}">
        </div>
        <div>
          <label>Ate</label><br>
          <input type="date" id="filter-ate" value="{data_max}">
        </div>
        <div style="display:flex;align-items:flex-end">
          <button onclick="aplicarFiltros()">Filtrar</button>
        </div>
      </div>
      <div style="max-height: 500px; overflow-y: auto;">
        <table>
          <thead><tr><th>Data</th><th>Perfil</th><th>Portal</th><th>Objeto</th><th>Regra</th><th>Valor</th></tr></thead>
          <tbody id="tbody-historico"></tbody>
        </table>
      </div>
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

<script>
const HISTORICO = {historico_json};

function fmtValor(v) {{
  if (v == null || v === 0) return '-';
  return 'R$ ' + v.toLocaleString('pt-BR');
}}

function escHtml(v) {{
  const div = document.createElement('div');
  div.textContent = String(v ?? '');
  return div.innerHTML;
}}

function aplicarFiltros() {{
  const perfil = document.getElementById('filter-perfil').value;
  const portal = document.getElementById('filter-portal').value;
  const desde = document.getElementById('filter-desde').value;
  const ate = document.getElementById('filter-ate').value;

  let filtrado = HISTORICO;
  if (perfil) filtrado = filtrado.filter(h => h.perfil === perfil);
  if (portal) filtrado = filtrado.filter(h => h.portal === portal);
  if (desde) filtrado = filtrado.filter(h => (h.visto_em || '').slice(0, 10) >= desde);
  if (ate) filtrado = filtrado.filter(h => (h.visto_em || '').slice(0, 10) <= ate);

  const tbody = document.getElementById('tbody-historico');
  document.getElementById('count-badge').textContent = filtrado.length;

  if (filtrado.length === 0) {{
    tbody.innerHTML = '<tr><td colspan="6">Nenhum item encontrado</td></tr>';
    return;
  }}

  tbody.innerHTML = filtrado.map(h => `
    <tr>
      <td>${{escHtml((h.visto_em || '').slice(0, 16))}}</td>
      <td>${{escHtml(h.perfil)}}</td>
      <td>${{escHtml(h.portal)}}</td>
      <td title="${{escHtml(h.objeto)}}">
        ${{escHtml((h.objeto || '').slice(0, 80))}}
      </td>
      <td>${{escHtml(h.regra)}}</td>
      <td class="valor">${{fmtValor(h.valor)}}</td>
    </tr>
  `).join('');
}}

document.addEventListener('DOMContentLoaded', () => {{
  aplicarFiltros();
}});
</script>
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
