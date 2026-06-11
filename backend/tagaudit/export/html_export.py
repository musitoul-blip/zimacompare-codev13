"""
export/html_export.py - F15: rapport HTML interactif ZimaTAG (complement de l'Excel).

Autoporte (inline CSS/JS, zero CDN). Consomme report_model comme SOURCE UNIQUE
du health score et des top-issues (meme calcul que l'Excel, pas de divergence),
et reutilise ExcelExporter pour l'enrichissement des resultats (zero duplication).
"""
import html as _html
import pandas as pd
from datetime import datetime
from core import config, logger

ROW_CAP = 1000               # lignes max affichees par table
SKIP_KEYS = {"music_tags"}   # dump brut complet -> reserve a l'Excel


def _prepare():
    """Charge master_scan.csv, lance les audits + enrichissement en reutilisant
    ExcelExporter (on ne re-implemente PAS la logique d'enrichissement)."""
    from export.excel_export import ExcelExporter
    from audit import AuditEngine
    csv_path = config.master_csv_path
    if not csv_path.exists():
        raise FileNotFoundError("master_scan.csv introuvable: %s" % csv_path)
    df = pd.read_csv(csv_path, sep=config.CSV_SEPARATOR,
                     encoding=config.CSV_ENCODING, low_memory=False)
    exp = ExcelExporter()
    exp.df_main = df
    exp.audit_results = AuditEngine(df).run_all_audits()
    exp.audit_results["music_tags"] = df
    exp._enrich_audit_results()
    return exp


def _score_color(score):
    if score >= 85:
        return "#2E7D32"
    if score >= 60:
        return "#F9A825"
    return "#C62828"


def _table_html(df):
    shown = df.head(ROW_CAP)
    try:
        t = shown.to_html(index=False, border=0, escape=True,
                          classes="audit-table", na_rep="")
    except Exception as e:
        return "<p class='err'>table indisponible: %s</p>" % _html.escape(str(e))
    if len(df) > ROW_CAP:
        t += "<p class='cap'>%d lignes au total, %d affichees.</p>" % (len(df), ROW_CAP)
    return t


def export_to_html():
    """Construit et retourne le rapport HTML complet (string autoportee)."""
    from export.excel_export import ExcelExporter
    from audit import report_model
    exp = _prepare()
    ar = exp.audit_results
    df = exp.df_main
    groups = ExcelExporter.SHEET_GROUPS
    weights = ExcelExporter.HEALTH_WEIGHTS
    score, penalties = report_model.compute_health_score(ar, df, groups, weights)
    top = report_model.compute_top_issues(ar, groups)
    total = len(df)
    color = _score_color(score)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    p = []
    p.append("<!doctype html><html lang='fr'><head><meta charset='utf-8'>")
    p.append("<meta name='viewport' content='width=device-width, initial-scale=1'>")
    p.append("<title>ZimaTAG - Rapport d'audit</title>")
    p.append("<style>" + _CSS + "</style></head><body>")

    # ----- Cockpit -----
    p.append("<header class='cockpit'>")
    p.append("<div class='cock-l'>")
    p.append("<h1>ZimaTAG &middot; Rapport d'audit</h1>")
    p.append("<p class='sub'>%d fichiers analyses &middot; genere le %s</p>" % (total, now))
    frac = max(0, min(100, score)) / 100.0
    w = int(round(frac * 260))
    p.append("<div class='score'>")
    p.append("<div class='scoreval' style='color:%s'>%d<span>/100</span></div>" % (color, score))
    p.append("<svg width='260' height='14' class='bar' role='img' aria-label='health score'>")
    p.append("<rect width='260' height='14' rx='7' fill='#e8e8ee'></rect>")
    p.append("<rect width='%d' height='14' rx='7' fill='%s'></rect></svg>" % (w, color))
    p.append("<div class='scorelbl'>Health score</div></div></div>")

    p.append("<div class='top'><h2>Top problemes</h2>")
    if top:
        mx = max((c for _, c, _ in top), default=1) or 1
        p.append("<ul class='topbars'>")
        for label, count, grp in top:
            bw = int(round((count / mx) * 100))
            p.append("<li><span class='tl'>%s</span>"
                     "<span class='tb'><span class='tbf' style='width:%d%%'></span></span>"
                     "<span class='tc'>%d</span></li>"
                     % (_html.escape(str(label)), bw, count))
        p.append("</ul>")
    else:
        p.append("<p class='ok'>Aucun probleme detecte. </p>")
    p.append("</div></header>")

    # ----- Sections par groupe -----
    p.append("<main>")
    for group_name, sheets in groups.items():
        if group_name == "cockpit":
            continue
        p.append("<section class='grp'><h2 class='grp-title'>%s</h2>" % _html.escape(str(group_name)))
        for sheet_name, data_key in sheets:
            if data_key in SKIP_KEYS:
                continue
            data = ar.get(data_key)
            n = report_model.get_row_count(ar, data_key)
            badge = "okb" if n == 0 else "warnb"
            p.append("<div class='card'>")
            p.append("<div class='card-h'><h3>%s</h3><span class='badge %s'>%d</span></div>"
                     % (_html.escape(str(sheet_name)), badge, n))
            if isinstance(data, pd.DataFrame) and not data.empty:
                p.append("<input class='flt' placeholder='filtrer ces lignes...' oninput='zimFilter(this)'>")
                p.append("<div class='tw'>" + _table_html(data) + "</div>")
            else:
                p.append("<p class='empty'>Rien a signaler.</p>")
            p.append("</div>")
        p.append("</section>")
    p.append("</main>")

    p.append("<footer>ZimaTAG &middot; rapport autoporte hors-ligne &middot; "
             "memes audits que l'export Excel</footer>")
    p.append("<script>" + _JS + "</script>")
    p.append("</body></html>")
    return "".join(p)


_CSS = r"""
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
color:#1a1a2e;background:#f4f5f9;line-height:1.45}
h1,h2,h3{margin:0}
.cockpit{display:flex;flex-wrap:wrap;gap:28px;align-items:center;justify-content:space-between;
padding:26px 30px;background:linear-gradient(135deg,#1F4E79,#2E86AB);color:#fff}
.cockpit h1{font-size:22px;font-weight:700}
.cockpit .sub{margin:4px 0 14px;opacity:.85;font-size:13px}
.score{display:flex;flex-direction:column;gap:6px}
.scoreval{font-size:40px;font-weight:800;line-height:1;background:#fff;padding:8px 16px;
border-radius:12px;display:inline-block;width:max-content}
.scoreval span{font-size:16px;font-weight:600;opacity:.6}
.bar{display:block}
.scorelbl{font-size:12px;text-transform:uppercase;letter-spacing:.08em;opacity:.85}
.top{min-width:320px;flex:1;background:rgba(255,255,255,.10);border-radius:14px;padding:16px 18px}
.top h2{font-size:14px;text-transform:uppercase;letter-spacing:.06em;margin-bottom:10px;opacity:.9}
.topbars{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:8px}
.topbars li{display:grid;grid-template-columns:1fr 120px 44px;align-items:center;gap:10px;font-size:13px}
.tl{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tb{background:rgba(255,255,255,.25);height:9px;border-radius:5px;overflow:hidden}
.tbf{display:block;height:100%;background:#FFD166}
.tc{text-align:right;font-variant-numeric:tabular-nums;font-weight:700}
.ok{font-size:14px}
main{max-width:1180px;margin:24px auto;padding:0 18px;display:flex;flex-direction:column;gap:26px}
.grp-title{font-size:13px;text-transform:uppercase;letter-spacing:.08em;color:#6b7080;
margin:0 0 12px 2px}
.grp{display:flex;flex-direction:column}
.card{background:#fff;border:1px solid #e6e7ee;border-radius:14px;padding:14px 16px;margin-bottom:14px;
box-shadow:0 1px 2px rgba(20,20,50,.04)}
.card-h{display:flex;align-items:center;gap:10px;margin-bottom:8px}
.card-h h3{font-size:15px;font-weight:650}
.badge{margin-left:auto;font-size:12px;font-weight:700;padding:2px 10px;border-radius:20px;
font-variant-numeric:tabular-nums}
.okb{background:#e6f4ea;color:#2E7D32}
.warnb{background:#fdecea;color:#C62828}
.empty{color:#8a8f9c;font-size:13px;margin:4px 0 2px}
.flt{width:100%;padding:7px 10px;margin:2px 0 10px;border:1px solid #d8dae3;border-radius:8px;
font-size:13px;outline:none}
.flt:focus{border-color:#2E86AB;box-shadow:0 0 0 3px rgba(46,134,171,.15)}
.tw{overflow:auto;max-height:430px;border:1px solid #eef0f5;border-radius:8px}
table.audit-table{border-collapse:collapse;width:100%;font-size:12.5px}
table.audit-table thead th{position:sticky;top:0;background:#f1f3f8;color:#3a3f50;text-align:left;
padding:7px 9px;border-bottom:1px solid #e0e3ec;white-space:nowrap;cursor:pointer}
table.audit-table tbody td{padding:6px 9px;border-bottom:1px solid #f1f2f7;
max-width:360px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
table.audit-table tbody tr:hover{background:#f8fafc}
.cap{font-size:12px;color:#8a8f9c;padding:6px 9px;margin:0}
.err{color:#C62828;font-size:13px}
footer{text-align:center;color:#9498a6;font-size:12px;padding:26px 12px 40px}
"""

_JS = r"""
function zimFilter(inp){
  var q=inp.value.toLowerCase();
  var tbl=inp.parentNode.querySelector('table');
  if(!tbl||!tbl.tBodies.length)return;
  var rows=tbl.tBodies[0].rows;
  for(var i=0;i<rows.length;i++){
    var r=rows[i];
    r.style.display=(r.innerText.toLowerCase().indexOf(q)>-1)?'':'none';
  }
}
document.addEventListener('click',function(e){
  var th=e.target.closest&&e.target.closest('table.audit-table thead th');
  if(!th)return;
  var tbl=th.closest('table');var idx=Array.prototype.indexOf.call(th.parentNode.children,th);
  var body=tbl.tBodies[0];if(!body)return;
  var rows=Array.prototype.slice.call(body.rows);
  var asc=th.getAttribute('data-asc')!=='1';
  rows.sort(function(a,b){
    var x=a.cells[idx]?a.cells[idx].innerText:'';var y=b.cells[idx]?b.cells[idx].innerText:'';
    var nx=parseFloat(x.replace(',','.')),ny=parseFloat(y.replace(',','.'));
    if(!isNaN(nx)&&!isNaN(ny))return asc?nx-ny:ny-nx;
    return asc?x.localeCompare(y):y.localeCompare(x);
  });
  rows.forEach(function(r){body.appendChild(r);});
  th.setAttribute('data-asc',asc?'1':'0');
});
"""
