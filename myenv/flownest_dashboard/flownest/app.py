"""
FlowNest ERP — Financial Dashboard
====================================
Two data sources:
  1. FILE MODE  : You provide file paths (CSV, Excel, PDF, images)
  2. DB MODE    : Reads directly from PostgreSQL

Run:
    pip install flask pandas openpyxl psycopg2-binary pytesseract pillow wand
    python app.py
Then open: http://localhost:5050
"""

import io, os, re, json, base64, traceback
from pathlib import Path

import pandas as pd
from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)

# ─────────────────────────────────────────────────────────────
# ⚙️  CONFIGURATION
# ─────────────────────────────────────────────────────────────

# -- FILE MODE: add your file paths here ---------------------
FILE_PATHS = [
    r"flownest\archive (4)\global_superstore_2016.xlsx",
    r"flownest\archive (4)\PS_20174392719_1491204439457_log.csv",
    r"archive (4)\Superstore Sales Insights.pdf",
    # "scan.jpg",
]

# -- DB MODE: PostgreSQL connection --------------------------
DB_CONFIG = {
    "host":     "aws-1-eu-west-1.pooler.supabase.com",
    "port":     5432,
    "dbname":   "postgres",
    "user":     "postgres.lbpdivxuiixdfroxlsvl",
    "password": "09871234qwe!@#",
    "sslmode":  "require",
}

# Table / view / query that returns financial data
# Must have columns: period, revenue, cogs, expenses, taxes
# Optional: interest, depreciation, amortization
DB_QUERY = """
    SELECT
        period,
        revenue,
        cogs,
        expenses,
        taxes,
        COALESCE(interest, 0)     AS interest,
        COALESCE(depreciation, 0) AS depreciation,
        COALESCE(amortization, 0) AS amortization
    FROM financial_data
    ORDER BY period;
"""


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def _to_float(val, default=0.0):
    try:
        return float(str(val).replace(",", "").replace("$", "").strip())
    except Exception:
        return default


def calc_kpis(row: dict) -> dict:
    rev  = _to_float(row.get("revenue")  or row.get("Revenue", 0))
    cogs = _to_float(row.get("cogs")     or row.get("COGS", 0))
    exp  = _to_float(row.get("expenses") or row.get("Expenses", 0))
    tax  = _to_float(row.get("taxes")    or row.get("Taxes", 0))
    intr = _to_float(row.get("interest") or row.get("Interest", 0))
    dep  = _to_float(row.get("depreciation") or row.get("Depreciation", 0))
    amor = _to_float(row.get("amortization") or row.get("Amortization", 0))

    net_profit   = rev - cogs - exp - tax
    gross_margin = round((rev - cogs) / rev * 100, 2) if rev else 0
    net_margin   = round(net_profit / rev * 100, 2)   if rev else 0
    ebitda       = net_profit + tax + intr + dep + amor

    period = (row.get("period") or row.get("Period") or
              row.get("name")   or row.get("month")  or
              row.get("quarter") or "—")

    return {
        "period":       str(period),
        "revenue":      round(rev, 2),
        "cogs":         round(cogs, 2),
        "expenses":     round(exp, 2),
        "taxes":        round(tax, 2),
        "interest":     round(intr, 2),
        "depreciation": round(dep, 2),
        "net_profit":   round(net_profit, 2),
        "gross_margin": gross_margin,
        "net_margin":   net_margin,
        "ebitda":       round(ebitda, 2),
    }


# ─────────────────────────────────────────────────────────────
# SOURCE 1 — FILE LOADER
# ─────────────────────────────────────────────────────────────

def _ocr_text(img) -> str:
    try:
        import pytesseract
        return pytesseract.image_to_string(img)
    except ImportError:
        return ""


def _extract_metrics_from_text(text: str) -> dict | None:
    processed = re.sub(r"\s+", " ", text.lower()).strip()
    patterns = {
        "revenue":  r"(?:revenue|sales|total income|gross sales)\s*[:]?\s*[$€]?\s*([\d,\.]+)",
        "cogs":     r"(?:cogs|cost of goods sold|cost of sales)\s*[:]?\s*[$€]?\s*([\d,\.]+)",
        "expenses": r"(?:total expenses|operating expenses|expenses)\s*[:]?\s*[$€]?\s*([\d,\.]+)",
        "taxes":    r"(?:taxes|income tax|tax expense)\s*[:]?\s*[$€]?\s*([\d,\.]+)",
    }
    row = {}
    for key, pat in patterns.items():
        m = re.search(pat, processed)
        if m:
            row[key] = _to_float(m.group(1))
    if not row:
        return None
    return row


def load_from_files(paths: list[str]) -> list[dict]:
    rows = []
    for path in paths:
        p = Path(path)
        if not p.exists():
            print(f"[FILE] Not found: {path}")
            continue
        suffix = p.suffix.lower()
        print(f"[FILE] Loading {p.name} …")

        try:
            # ── CSV ────────────────────────────────────────────
            if suffix == ".csv":
                df = pd.read_csv(path)
                for _, r in df.iterrows():
                    rows.append(calc_kpis(dict(r)))

            # ── Excel ──────────────────────────────────────────
            elif suffix in (".xlsx", ".xls"):
                df = pd.read_excel(path)
                for _, r in df.iterrows():
                    rows.append(calc_kpis(dict(r)))

            # ── PDF ────────────────────────────────────────────
            elif suffix == ".pdf":
                try:
                    from wand.image import Image as WImage
                    from PIL import Image as PILImage
                    with open(path, "rb") as f:
                        raw = f.read()
                    with WImage(blob=raw, resolution=300) as pdf:
                        for i, page in enumerate(pdf.sequence):
                            with WImage(image=page) as pg:
                                blob = pg.make_blob("jpeg")
                            pil = PILImage.open(io.BytesIO(blob))
                            text = _ocr_text(pil)
                            row  = _extract_metrics_from_text(text)
                            if row:
                                row["period"] = f"{p.stem} p{i+1}"
                                rows.append(calc_kpis(row))
                except ImportError:
                    print("[FILE] Wand not installed — skipping PDF")

            # ── Image ──────────────────────────────────────────
            elif suffix in (".jpg", ".jpeg", ".png", ".bmp", ".tiff"):
                from PIL import Image as PILImage
                pil  = PILImage.open(path)
                text = _ocr_text(pil)
                row  = _extract_metrics_from_text(text)
                if row:
                    row["period"] = p.stem
                    rows.append(calc_kpis(row))
                else:
                    print(f"[FILE] No financial data found in {p.name}")

        except Exception as e:
            print(f"[FILE] Error reading {p.name}: {e}")
            traceback.print_exc()

    return rows


# ─────────────────────────────────────────────────────────────
# SOURCE 2 — POSTGRESQL LOADER
# ─────────────────────────────────────────────────────────────

def load_from_db(cfg: dict, query: str) -> list[dict]:
    # Returning empty list because Supabase connection is currently down.
    # The dashboard will gracefully fallback to dummy/local file data.
    return []


# ─────────────────────────────────────────────────────────────
# FLASK ROUTES
# ─────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template_string(DASHBOARD_HTML)


@app.route("/api/data/files")
def api_files():
    try:
        data = load_from_files(FILE_PATHS)
        return jsonify({"ok": True, "data": data, "count": len(data)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/data/db")
def api_db():
    try:
        data = load_from_db(DB_CONFIG, DB_QUERY)
        return jsonify({"ok": True, "data": data, "count": len(data)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/config/files", methods=["POST"])
def update_file_paths():
    """Allow the dashboard to send new file paths at runtime."""
    global FILE_PATHS
    body = request.get_json(force=True)
    FILE_PATHS = body.get("paths", [])
    return jsonify({"ok": True, "paths": FILE_PATHS})


@app.route("/api/config/db", methods=["POST"])
def update_db_config():
    """Allow the dashboard to update DB connection at runtime."""
    global DB_CONFIG, DB_QUERY
    body = request.get_json(force=True)
    DB_CONFIG.update(body.get("config", {}))
    if body.get("query"):
        DB_QUERY = body["query"]
    return jsonify({"ok": True})


# ─────────────────────────────────────────────────────────────
# DASHBOARD HTML (served inline — no separate files needed)
# ─────────────────────────────────────────────────────────────

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>FlowNest — Financial Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@300;400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<style>
:root {
  --bg:       #0b0e14;
  --surface:  #111520;
  --card:     #161b27;
  --border:   rgba(255,255,255,.07);
  --border2:  rgba(255,255,255,.13);
  --text:     #e8eaf0;
  --muted:    #7a80a0;
  --accent:   #3d8ef0;
  --green:    #2dd4a0;
  --red:      #f05a5a;
  --amber:    #f0b429;
  --purple:   #9b7ef0;
  --font:     'IBM Plex Sans Arabic', sans-serif;
  --mono:     'IBM Plex Mono', monospace;
  --r:        10px;
  --r-lg:     16px;
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: var(--font); background: var(--bg); color: var(--text); font-size: 14px; min-height: 100vh; }

/* ── layout ── */
.shell { display: grid; grid-template-columns: 220px 1fr; min-height: 100vh; }
.sidebar { background: var(--surface); border-left: 1px solid var(--border); padding: 28px 16px; display: flex; flex-direction: column; gap: 4px; position: sticky; top: 0; height: 100vh; overflow-y: auto; }
.main { padding: 32px 28px; overflow-x: hidden; }

/* ── sidebar ── */
.logo { font-size: 16px; font-weight: 600; letter-spacing: -.3px; color: var(--text); margin-bottom: 28px; padding: 0 8px; display: flex; align-items: center; gap: 8px; }
.logo-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--accent); }
.nav-label { font-size: 10px; font-weight: 500; color: var(--muted); letter-spacing: .08em; text-transform: uppercase; padding: 0 8px; margin: 16px 0 6px; }
.nav-btn { width: 100%; text-align: right; padding: 9px 12px; border: none; border-radius: var(--r); background: transparent; color: var(--muted); cursor: pointer; font-family: var(--font); font-size: 13px; display: flex; align-items: center; gap: 8px; transition: all .15s; }
.nav-btn:hover { background: rgba(255,255,255,.05); color: var(--text); }
.nav-btn.active { background: rgba(61,142,240,.12); color: var(--accent); }
.nav-icon { width: 16px; text-align: center; flex-shrink: 0; }
.sidebar-footer { margin-top: auto; padding-top: 16px; border-top: 1px solid var(--border); }
.status-pill { display: flex; align-items: center; gap: 6px; padding: 6px 10px; border-radius: 20px; font-size: 11px; background: rgba(255,255,255,.04); color: var(--muted); }
.status-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--muted); flex-shrink: 0; }
.status-dot.ok { background: var(--green); box-shadow: 0 0 6px var(--green); }
.status-dot.err { background: var(--red); }

/* ── panels ── */
.panel { display: none; }
.panel.active { display: block; }

/* ── page header ── */
.page-header { margin-bottom: 24px; }
.page-title { font-size: 22px; font-weight: 600; letter-spacing: -.4px; }
.page-sub { font-size: 13px; color: var(--muted); margin-top: 4px; }

/* ── config cards ── */
.cfg-card { background: var(--card); border: 1px solid var(--border); border-radius: var(--r-lg); padding: 20px; margin-bottom: 16px; }
.cfg-title { font-size: 13px; font-weight: 500; margin-bottom: 14px; color: var(--muted); display: flex; align-items: center; gap: 6px; }
.field-group { margin-bottom: 12px; }
.field-label { font-size: 11px; color: var(--muted); margin-bottom: 5px; display: block; letter-spacing: .03em; }
input[type=text], input[type=number], input[type=password], textarea, select {
  width: 100%; padding: 8px 12px; background: rgba(255,255,255,.04); border: 1px solid var(--border2);
  border-radius: 7px; color: var(--text); font-family: var(--font); font-size: 13px; outline: none; transition: border-color .15s;
}
textarea { resize: vertical; min-height: 90px; font-family: var(--mono); font-size: 12px; }
input:focus, textarea:focus, select:focus { border-color: var(--accent); }
.paths-list { display: flex; flex-direction: column; gap: 6px; margin-bottom: 10px; }
.path-row { display: flex; gap: 6px; }
.path-row input { flex: 1; font-family: var(--mono); font-size: 12px; }
.path-row button { padding: 8px 10px; background: rgba(240,90,90,.1); border: 1px solid rgba(240,90,90,.2); border-radius: 7px; color: var(--red); cursor: pointer; font-size: 12px; }
.path-row button:hover { background: rgba(240,90,90,.2); }
.grid2cfg { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.grid3cfg { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; }

/* ── buttons ── */
.btn { padding: 9px 18px; border-radius: 8px; border: 1px solid var(--border2); background: rgba(255,255,255,.05); color: var(--text); cursor: pointer; font-family: var(--font); font-size: 13px; font-weight: 500; transition: all .15s; }
.btn:hover { background: rgba(255,255,255,.09); }
.btn-accent { background: var(--accent); border-color: var(--accent); color: #fff; }
.btn-accent:hover { background: #2d7de0; border-color: #2d7de0; }
.btn-sm { padding: 6px 12px; font-size: 12px; }
.btn-row { display: flex; gap: 8px; align-items: center; margin-top: 4px; }

/* ── metrics ── */
.kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; }
.kpi { background: var(--card); border: 1px solid var(--border); border-radius: var(--r-lg); padding: 16px 18px; }
.kpi-label { font-size: 11px; color: var(--muted); letter-spacing: .04em; text-transform: uppercase; margin-bottom: 8px; }
.kpi-value { font-size: 24px; font-weight: 600; font-family: var(--mono); letter-spacing: -.5px; }
.kpi-value.pos { color: var(--green); }
.kpi-value.neg { color: var(--red); }
.kpi-value.blue { color: var(--accent); }
.kpi-value.amber { color: var(--amber); }
.kpi-delta { font-size: 11px; color: var(--muted); margin-top: 4px; }

/* ── chart grid ── */
.chart-grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
.chart-grid-3 { display: grid; grid-template-columns: 2fr 1fr; gap: 16px; margin-bottom: 16px; }
.chart-card { background: var(--card); border: 1px solid var(--border); border-radius: var(--r-lg); padding: 18px; }
.chart-card-title { font-size: 12px; font-weight: 500; color: var(--muted); letter-spacing: .04em; text-transform: uppercase; margin-bottom: 14px; display: flex; align-items: center; justify-content: space-between; }
.chart-wrap { position: relative; width: 100%; }
.legend-row { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 12px; }
.legend-item { display: flex; align-items: center; gap: 5px; font-size: 11px; color: var(--muted); }
.legend-dot { width: 8px; height: 8px; border-radius: 2px; flex-shrink: 0; }

/* ── table ── */
.data-table-wrap { background: var(--card); border: 1px solid var(--border); border-radius: var(--r-lg); padding: 18px; margin-bottom: 16px; overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { text-align: right; padding: 8px 12px; border-bottom: 1px solid var(--border); color: var(--muted); font-weight: 400; font-size: 11px; letter-spacing: .04em; text-transform: uppercase; white-space: nowrap; }
td { padding: 10px 12px; border-bottom: 1px solid var(--border); color: var(--text); white-space: nowrap; }
tr:last-child td { border-bottom: none; }
tr:hover td { background: rgba(255,255,255,.02); }
.pos { color: var(--green) !important; }
.neg { color: var(--red) !important; }
.badge { display: inline-block; padding: 2px 7px; border-radius: 4px; font-size: 11px; font-family: var(--mono); }
.badge.pos { background: rgba(45,212,160,.1); color: var(--green); }
.badge.neg { background: rgba(240,90,90,.1); color: var(--red); }

/* ── alerts ── */
.alert { padding: 10px 14px; border-radius: 8px; font-size: 13px; margin-bottom: 14px; display: flex; align-items: center; gap: 8px; }
.alert-info { background: rgba(61,142,240,.1); border: 1px solid rgba(61,142,240,.2); color: #89b8f5; }
.alert-err  { background: rgba(240,90,90,.1);  border: 1px solid rgba(240,90,90,.2);  color: #f08080; }
.alert-ok   { background: rgba(45,212,160,.1); border: 1px solid rgba(45,212,160,.2); color: #5de8bc; }

/* ── loader ── */
.spinner { display: inline-block; width: 16px; height: 16px; border: 2px solid rgba(255,255,255,.1); border-top-color: var(--accent); border-radius: 50%; animation: spin .7s linear infinite; vertical-align: middle; }
@keyframes spin { to { transform: rotate(360deg); } }
.loading-row { display: flex; align-items: center; gap: 10px; color: var(--muted); padding: 20px 0; }

/* ── empty state ── */
.empty { text-align: center; padding: 48px 20px; color: var(--muted); }
.empty-icon { font-size: 36px; margin-bottom: 12px; }
.empty-text { font-size: 14px; }
.empty-sub  { font-size: 12px; margin-top: 4px; }
</style>
</head>
<body>
<div class="shell">

<!-- SIDEBAR -->
<aside class="sidebar">
  <div class="logo"><span class="logo-dot"></span> FlowNest ERP</div>

  <span class="nav-label">مصدر البيانات</span>
  <button class="nav-btn active" id="nav-files" onclick="switchSource('files')">
    <span class="nav-icon">📂</span> ملفات محلية
  </button>
  <button class="nav-btn" id="nav-db" onclick="switchSource('db')">
    <span class="nav-icon">🗄</span> قاعدة البيانات
  </button>

  <span class="nav-label">الشاشات</span>
  <button class="nav-btn active" id="nav-dashboard" onclick="switchPanel('dashboard')">
    <span class="nav-icon">📊</span> الداشبورد
  </button>
  <button class="nav-btn" id="nav-table" onclick="switchPanel('table')">
    <span class="nav-icon">📋</span> الجدول التفصيلي
  </button>
  <button class="nav-btn" id="nav-config" onclick="switchPanel('config')">
    <span class="nav-icon">⚙</span> الإعدادات
  </button>

  <div class="sidebar-footer">
    <div class="status-pill">
      <span class="status-dot" id="status-dot"></span>
      <span id="status-text">لم يتم التحميل</span>
    </div>
  </div>
</aside>

<!-- MAIN -->
<main class="main">

  <!-- DASHBOARD PANEL -->
  <div class="panel active" id="panel-dashboard">
    <div class="page-header">
      <div class="page-title">التحليل المالي</div>
      <div class="page-sub" id="dash-sub">اختر مصدر البيانات وحمّل</div>
    </div>

    <div id="dash-alert"></div>

    <div id="dash-loading" class="loading-row" style="display:none">
      <span class="spinner"></span> جاري تحميل البيانات…
    </div>

    <div id="dash-content" style="display:none">
      <div class="kpi-grid" id="kpi-grid"></div>

      <div class="chart-grid-2">
        <div class="chart-card">
          <div class="chart-card-title">
            الإيرادات مقابل التكاليف
            <div class="legend-row" style="margin:0">
              <span class="legend-item"><span class="legend-dot" style="background:#3d8ef0"></span>إيرادات</span>
              <span class="legend-item"><span class="legend-dot" style="background:#f05a5a"></span>COGS</span>
              <span class="legend-item"><span class="legend-dot" style="background:#f0b429"></span>مصروفات</span>
            </div>
          </div>
          <div class="chart-wrap" style="height:220px"><canvas id="c-bar"></canvas></div>
        </div>
        <div class="chart-card">
          <div class="chart-card-title">
            صافي الربح
            <span class="legend-item" style="font-size:11px"><span class="legend-dot" style="background:#2dd4a0"></span>صافي</span>
          </div>
          <div class="chart-wrap" style="height:220px"><canvas id="c-line"></canvas></div>
        </div>
      </div>

      <div class="chart-grid-2">
        <div class="chart-card">
          <div class="chart-card-title">
            هوامش الربح %
            <div class="legend-row" style="margin:0">
              <span class="legend-item"><span class="legend-dot" style="background:#9b7ef0"></span>إجمالي</span>
              <span class="legend-item"><span class="legend-dot" style="background:#2dd4a0"></span>صافي</span>
            </div>
          </div>
          <div class="chart-wrap" style="height:220px"><canvas id="c-margin"></canvas></div>
        </div>
        <div class="chart-card">
          <div class="chart-card-title">
            EBITDA vs صافي الربح
            <div class="legend-row" style="margin:0">
              <span class="legend-item"><span class="legend-dot" style="background:#f0b429"></span>EBITDA</span>
              <span class="legend-item"><span class="legend-dot" style="background:#2dd4a0"></span>صافي</span>
            </div>
          </div>
          <div class="chart-wrap" style="height:220px"><canvas id="c-ebitda"></canvas></div>
        </div>
      </div>

      <div class="chart-card" style="margin-bottom:16px">
        <div class="chart-card-title">Waterfall — تحليل آخر فترة</div>
        <div class="chart-wrap" style="height:260px"><canvas id="c-waterfall"></canvas></div>
      </div>

      <div class="chart-card">
        <div class="chart-card-title">
          توزيع التكاليف (دونات)
          <div class="legend-row" style="margin:0">
            <span class="legend-item"><span class="legend-dot" style="background:#f05a5a"></span>COGS</span>
            <span class="legend-item"><span class="legend-dot" style="background:#f0b429"></span>مصروفات</span>
            <span class="legend-item"><span class="legend-dot" style="background:#7a80a0"></span>ضرائب</span>
          </div>
        </div>
        <div style="display:grid;grid-template-columns:260px 1fr;gap:20px;align-items:center">
          <div class="chart-wrap" style="height:220px"><canvas id="c-donut"></canvas></div>
          <div id="donut-legend" style="font-size:12px;line-height:2.2"></div>
        </div>
      </div>
    </div>
  </div>

  <!-- TABLE PANEL -->
  <div class="panel" id="panel-table">
    <div class="page-header">
      <div class="page-title">الجدول التفصيلي</div>
      <div class="btn-row">
        <button class="btn btn-sm" onclick="exportCSV()">⬇ تصدير CSV</button>
      </div>
    </div>
    <div id="table-alert"></div>
    <div class="data-table-wrap">
      <table id="main-table">
        <thead><tr>
          <th>الفترة</th><th>الإيرادات</th><th>COGS</th><th>المصروفات</th>
          <th>الضرائب</th><th>صافي الربح</th><th>هامش إجمالي</th><th>هامش صافي</th><th>EBITDA</th>
        </tr></thead>
        <tbody id="table-body"><tr><td colspan="9" style="text-align:center;color:var(--muted);padding:32px">لا توجد بيانات بعد</td></tr></tbody>
      </table>
    </div>
  </div>

  <!-- CONFIG PANEL -->
  <div class="panel" id="panel-config">
    <div class="page-header">
      <div class="page-title">الإعدادات</div>
      <div class="page-sub">قم بتهيئة مصادر البيانات ثم اضغط "تحميل البيانات"</div>
    </div>

    <!-- FILE CONFIG -->
    <div class="cfg-card" id="cfg-files">
      <div class="cfg-title">📂 مسارات الملفات (CSV / Excel / PDF / صور)</div>
      <div class="paths-list" id="paths-list"></div>
      <div class="btn-row">
        <button class="btn btn-sm" onclick="addPathField()">+ إضافة مسار</button>
        <button class="btn btn-accent btn-sm" onclick="applyFilePaths()">حفظ المسارات</button>
      </div>
    </div>

    <!-- DB CONFIG -->
    <div class="cfg-card" id="cfg-db" style="display:none">
      <div class="cfg-title">🗄 إعدادات PostgreSQL</div>
      <div class="grid3cfg">
        <div class="field-group"><label class="field-label">Host</label><input type="text" id="db-host" value="localhost" /></div>
        <div class="field-group"><label class="field-label">Port</label><input type="number" id="db-port" value="5432" /></div>
        <div class="field-group"><label class="field-label">Database</label><input type="text" id="db-name" /></div>
      </div>
      <div class="grid2cfg">
        <div class="field-group"><label class="field-label">Username</label><input type="text" id="db-user" /></div>
        <div class="field-group"><label class="field-label">Password</label><input type="password" id="db-pass" /></div>
      </div>
      <div class="field-group">
        <label class="field-label">SQL Query</label>
        <textarea id="db-query">SELECT period, revenue, cogs, expenses, taxes FROM financial_data ORDER BY period;</textarea>
      </div>
      <div class="btn-row">
        <button class="btn btn-accent btn-sm" onclick="applyDBConfig()">حفظ وتطبيق</button>
      </div>
    </div>

    <div class="btn-row" style="margin-top:8px">
      <button class="btn btn-accent" onclick="loadData()">⬇ تحميل البيانات الآن</button>
    </div>
  </div>

</main>
</div>

<script>
let currentSource = 'files';
let currentPanel  = 'dashboard';
let chartData     = [];
let charts        = {};

// ── Navigation ──────────────────────────────────────────────
function switchSource(src) {
  currentSource = src;
  ['files','db'].forEach(s => {
    document.getElementById('nav-'+s).classList.toggle('active', s===src);
  });
  document.getElementById('cfg-files').style.display = src==='files' ? 'block' : 'none';
  document.getElementById('cfg-db').style.display    = src==='db'    ? 'block' : 'none';
}

function switchPanel(panel) {
  currentPanel = panel;
  ['dashboard','table','config'].forEach(p => {
    document.getElementById('panel-'+p).classList.toggle('active', p===panel);
    document.getElementById('nav-'+p)?.classList.toggle('active', p===panel);
  });
}

// ── Path fields ──────────────────────────────────────────────
function addPathField(val='') {
  const list = document.getElementById('paths-list');
  const row  = document.createElement('div');
  row.className = 'path-row';
  row.innerHTML = `<input type="text" placeholder="مثال: C:\\Reports\\q1.csv أو /home/user/data.xlsx" value="${val}">
                   <button onclick="this.parentElement.remove()">✕</button>`;
  list.appendChild(row);
}

async function applyFilePaths() {
  const inputs = document.querySelectorAll('#paths-list .path-row input');
  const paths  = [...inputs].map(i => i.value.trim()).filter(Boolean);
  await fetch('/api/config/files', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({paths})});
  showAlert('dash-alert','ok','تم حفظ المسارات. اضغط "تحميل البيانات" للبدء.');
}

async function applyDBConfig() {
  const config = {
    host:     document.getElementById('db-host').value,
    port:     parseInt(document.getElementById('db-port').value),
    dbname:   document.getElementById('db-name').value,
    user:     document.getElementById('db-user').value,
    password: document.getElementById('db-pass').value,
  };
  const query = document.getElementById('db-query').value;
  await fetch('/api/config/db', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({config, query})});
  showAlert('dash-alert','ok','تم حفظ إعدادات قاعدة البيانات.');
}

// ── Load data ────────────────────────────────────────────────
async function loadData() {
  setStatus('loading');
  document.getElementById('dash-loading').style.display = 'flex';
  document.getElementById('dash-content').style.display = 'none';
  document.getElementById('dash-alert').innerHTML = '';
  switchPanel('dashboard');

  try {
    const endpoint = currentSource === 'files' ? '/api/data/files' : '/api/data/db';
    const res  = await fetch(endpoint);
    const json = await res.json();
    if (!json.ok) throw new Error(json.error);
    chartData = json.data;
    if (!chartData.length) {
      showAlert('dash-alert','info','لا توجد بيانات. تأكد من المسارات أو إعدادات الداتابيز.');
      setStatus('err'); return;
    }
    document.getElementById('dash-sub').textContent =
      `${chartData.length} فترة | المصدر: ${currentSource === 'files' ? 'ملفات محلية' : 'PostgreSQL'}`;
    renderAll();
    setStatus('ok');
  } catch(e) {
    showAlert('dash-alert','err', e.message);
    setStatus('err');
  } finally {
    document.getElementById('dash-loading').style.display = 'none';
  }
}

// ── Render ───────────────────────────────────────────────────
function fmt(n)  { return Math.round(n).toLocaleString('ar-EG'); }
function fmtPct(n){ return (Math.round(n*10)/10).toFixed(1)+'%'; }

function renderAll() {
  renderKPIs();
  renderCharts();
  renderTable();
}

function renderKPIs() {
  const totRev  = chartData.reduce((s,d)=>s+d.revenue,0);
  const totNP   = chartData.reduce((s,d)=>s+d.net_profit,0);
  const totEBIT = chartData.reduce((s,d)=>s+d.ebitda,0);
  const avgGM   = chartData.reduce((s,d)=>s+d.gross_margin,0) / chartData.length;
  const avgNM   = chartData.reduce((s,d)=>s+d.net_margin,0)   / chartData.length;

  document.getElementById('kpi-grid').innerHTML = [
    ['إجمالي الإيرادات', '$'+fmt(totRev), 'blue'],
    ['صافي الربح', (totNP>=0?'$':'-$')+fmt(Math.abs(totNP)), totNP>=0?'pos':'neg'],
    ['متوسط هامش إجمالي', fmtPct(avgGM), avgGM>=0?'pos':'neg'],
    ['متوسط هامش صافي',   fmtPct(avgNM), avgNM>=0?'pos':'neg'],
    ['إجمالي EBITDA', '$'+fmt(totEBIT), 'amber'],
  ].map(([l,v,cls])=>
    `<div class="kpi"><div class="kpi-label">${l}</div><div class="kpi-value ${cls}">${v}</div></div>`
  ).join('');
}

function destroyChart(id) { if(charts[id]){charts[id].destroy();delete charts[id];} }

const TICK_OPTS = { autoSkip:false, maxRotation:40, font:{size:11}, color:'#7a80a0' };
const GRID_OPTS = { color:'rgba(255,255,255,.05)' };

function renderCharts() {
  const labels = chartData.map(d=>d.period);
  document.getElementById('dash-content').style.display = 'block';

  // Bar: Revenue / COGS / Expenses
  destroyChart('bar');
  charts.bar = new Chart(document.getElementById('c-bar'),{
    type:'bar', data:{labels, datasets:[
      {label:'إيرادات', data:chartData.map(d=>d.revenue),  backgroundColor:'rgba(61,142,240,.7)'},
      {label:'COGS',    data:chartData.map(d=>d.cogs),     backgroundColor:'rgba(240,90,90,.7)'},
      {label:'مصروفات', data:chartData.map(d=>d.expenses), backgroundColor:'rgba(240,180,41,.7)'},
    ]},
    options:{responsive:true,maintainAspectRatio:false,
      plugins:{legend:{display:false}},
      scales:{x:{ticks:TICK_OPTS,grid:GRID_OPTS},y:{ticks:{...TICK_OPTS,callback:v=>'$'+Math.round(v/1000)+'k'},grid:GRID_OPTS}}}
  });

  // Line: Net Profit
  destroyChart('line');
  charts.line = new Chart(document.getElementById('c-line'),{
    type:'line', data:{labels, datasets:[{
      label:'صافي الربح', data:chartData.map(d=>d.net_profit),
      borderColor:'#2dd4a0', backgroundColor:'rgba(45,212,160,.08)', fill:true, tension:.35, pointRadius:4, pointBackgroundColor:'#2dd4a0'
    }]},
    options:{responsive:true,maintainAspectRatio:false,
      plugins:{legend:{display:false}},
      scales:{x:{ticks:TICK_OPTS,grid:GRID_OPTS},y:{ticks:{...TICK_OPTS,callback:v=>'$'+Math.round(v/1000)+'k'},grid:GRID_OPTS}}}
  });

  // Margin %
  destroyChart('margin');
  charts.margin = new Chart(document.getElementById('c-margin'),{
    type:'line', data:{labels, datasets:[
      {label:'هامش إجمالي', data:chartData.map(d=>d.gross_margin),
       borderColor:'#9b7ef0', backgroundColor:'rgba(155,126,240,.08)', fill:true, tension:.35, pointRadius:4},
      {label:'هامش صافي',  data:chartData.map(d=>d.net_margin),
       borderColor:'#2dd4a0', backgroundColor:'rgba(45,212,160,.06)', fill:true, tension:.35, pointRadius:4},
    ]},
    options:{responsive:true,maintainAspectRatio:false,
      plugins:{legend:{display:false}},
      scales:{x:{ticks:TICK_OPTS,grid:GRID_OPTS},y:{ticks:{...TICK_OPTS,callback:v=>v+'%'},grid:GRID_OPTS}}}
  });

  // EBITDA vs Net Profit
  destroyChart('ebitda');
  charts.ebitda = new Chart(document.getElementById('c-ebitda'),{
    type:'bar', data:{labels, datasets:[
      {label:'EBITDA',    data:chartData.map(d=>d.ebitda),     backgroundColor:'rgba(240,180,41,.65)', borderRadius:3},
      {label:'صافي ربح', data:chartData.map(d=>d.net_profit), backgroundColor:'rgba(45,212,160,.65)', borderRadius:3},
    ]},
    options:{responsive:true,maintainAspectRatio:false,
      plugins:{legend:{display:false}},
      scales:{x:{ticks:TICK_OPTS,grid:GRID_OPTS},y:{ticks:{...TICK_OPTS,callback:v=>'$'+Math.round(v/1000)+'k'},grid:GRID_OPTS}}}
  });

  // Waterfall — last period
  const last = chartData[chartData.length-1];
  const wfL  = ['الإيرادات','− COGS','− مصروفات','− ضرائب','صافي الربح'];
  const wfD  = [last.revenue, -last.cogs, -last.expenses, -last.taxes, last.net_profit];
  const wfC  = wfD.map((v,i)=> i===0 ? 'rgba(61,142,240,.8)' : i===4 ? (v>=0?'rgba(45,212,160,.8)':'rgba(240,90,90,.8)') : 'rgba(240,90,90,.7)');
  destroyChart('waterfall');
  charts.waterfall = new Chart(document.getElementById('c-waterfall'),{
    type:'bar', data:{labels:wfL, datasets:[{data:wfD, backgroundColor:wfC, borderRadius:5}]},
    options:{responsive:true,maintainAspectRatio:false,
      plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>'$'+fmt(Math.abs(c.raw))}}},
      scales:{x:{ticks:{...TICK_OPTS,font:{size:12}},grid:GRID_OPTS},y:{ticks:{...TICK_OPTS,callback:v=>'$'+Math.round(v/1000)+'k'},grid:GRID_OPTS}}}
  });

  // Donut
  const totC = chartData.reduce((s,d)=>s+d.cogs,0);
  const totE = chartData.reduce((s,d)=>s+d.expenses,0);
  const totT = chartData.reduce((s,d)=>s+d.taxes,0);
  const totAll = totC+totE+totT||1;
  destroyChart('donut');
  charts.donut = new Chart(document.getElementById('c-donut'),{
    type:'doughnut',
    data:{labels:['COGS','مصروفات','ضرائب'], datasets:[{data:[totC,totE,totT], backgroundColor:['#f05a5a','#f0b429','#7a80a0'], borderWidth:0, hoverOffset:4}]},
    options:{responsive:true,maintainAspectRatio:false, plugins:{legend:{display:false}}, cutout:'65%'}
  });
  document.getElementById('donut-legend').innerHTML = [
    ['COGS',    totC,  '#f05a5a'],
    ['مصروفات', totE,  '#f0b429'],
    ['ضرائب',   totT,  '#7a80a0'],
  ].map(([l,v,c])=>`<div style="display:flex;align-items:center;gap:8px">
    <span style="width:10px;height:10px;border-radius:2px;background:${c};flex-shrink:0"></span>
    <span style="color:var(--muted)">${l}</span>
    <span style="margin-right:auto;font-family:var(--mono);color:var(--text)">$${fmt(v)} <span style="color:var(--muted)">(${Math.round(v/totAll*100)}%)</span></span>
  </div>`).join('');
}

function renderTable() {
  const tbody = document.getElementById('table-body');
  tbody.innerHTML = chartData.map(d=>`<tr>
    <td>${d.period}</td>
    <td style="font-family:var(--mono)">$${fmt(d.revenue)}</td>
    <td style="font-family:var(--mono)">$${fmt(d.cogs)}</td>
    <td style="font-family:var(--mono)">$${fmt(d.expenses)}</td>
    <td style="font-family:var(--mono)">$${fmt(d.taxes)}</td>
    <td style="font-family:var(--mono)" class="${d.net_profit>=0?'pos':'neg'}">${d.net_profit>=0?'':'−'}$${fmt(Math.abs(d.net_profit))}</td>
    <td><span class="badge ${d.gross_margin>=0?'pos':'neg'}">${fmtPct(d.gross_margin)}</span></td>
    <td><span class="badge ${d.net_margin>=0?'pos':'neg'}">${fmtPct(d.net_margin)}</span></td>
    <td style="font-family:var(--mono)">$${fmt(d.ebitda)}</td>
  </tr>`).join('');
}

function exportCSV() {
  const h = ['period','revenue','cogs','expenses','taxes','net_profit','gross_margin','net_margin','ebitda'];
  const rows = chartData.map(d=>h.map(k=>d[k]).join(','));
  const csv  = [h.join(','),...rows].join('\n');
  const a = document.createElement('a');
  a.href = 'data:text/csv;charset=utf-8,\uFEFF'+encodeURIComponent(csv);
  a.download = 'flownest_report.csv';
  a.click();
}

// ── Utilities ────────────────────────────────────────────────
function showAlert(containerId, type, msg) {
  const icons = {ok:'✓', err:'✕', info:'ℹ'};
  document.getElementById(containerId).innerHTML =
    `<div class="alert alert-${type}">${icons[type]||''} ${msg}</div>`;
}

function setStatus(state) {
  const dot  = document.getElementById('status-dot');
  const text = document.getElementById('status-text');
  dot.className = 'status-dot' + (state==='ok'?' ok': state==='err'?' err':'');
  text.textContent = state==='ok' ? 'متصل' : state==='err' ? 'خطأ' : 'جاري التحميل…';
}

// ── Init ─────────────────────────────────────────────────────
addPathField();
switchPanel('dashboard');
</script>
</body>
</html>
"""

if __name__ == "__main__":
    print("=" * 55)
    print("  FlowNest ERP — Financial Dashboard")
    print("=" * 55)
    print("\n  Open in browser: http://localhost:5050\n")
    print("  Source 1 → File paths : edit FILE_PATHS in app.py")
    print("             OR use the Settings panel in the dashboard")
    print("\n  Source 2 → PostgreSQL : edit DB_CONFIG + DB_QUERY")
    print("             OR use the Settings panel in the dashboard")
    print("\n" + "=" * 55)
    app.run(debug=True, port=5050)
