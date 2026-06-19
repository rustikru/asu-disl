from __future__ import annotations

BASE_HTML = """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ title }}</title>
  <style>
    :root {
      --bg: #f4f7fb;
      --panel: #ffffff;
      --panel-soft: #f8fbff;
      --text: {{ ui_preferences.font_color|default("#182433") }};
      --muted: {{ ui_preferences.font_color_soft|default("rgba(24,36,51,.76)") }};
      --line: #dce4ee;
      --line-soft: #edf2f7;
      --accent: {{ ui_preferences.accent_color|default("#2456d4") }};
      --accent-soft: {{ ui_preferences.accent_soft|default("rgba(36,86,212,.12)") }};
      --danger: #c73b3b;
      --danger-soft: #fff1f1;
      --danger-border: #f0c9c9;
      --road: #f5f9ff;
      --station: #fcfdff;
      --shadow: 0 10px 28px rgba(20, 37, 63, .06);
      --radius: 10px;
      --mono: Consolas, "SFMono-Regular", ui-monospace, monospace;
      --group-border: #c9d5e8;
      --cargo-border: #e7edf5;
      --progress-low: #d9534f;
      --progress-mid: #f0ad4e;
      --progress-high: #3aa76d;
    }

    * { box-sizing: border-box; }
    html, body { margin: 0; }

    body {
      font-family: Inter, "Segoe UI", Arial, sans-serif;
      color: var(--text);
      background: linear-gradient(180deg, #f8fbff 0%, var(--bg) 100%);
      min-height: 100vh;
    }

    .shell { max-width: 1480px; margin: 0 auto; padding: 12px; }
    body.theme-dark { --bg: #17212e; --panel: #223043; --panel-soft: #27374c; --text: #eef4ff; --muted: #a4b5ca; --line: #39506a; --line-soft: #2d4057; --shadow: 0 14px 30px rgba(4, 10, 18, .35); background: linear-gradient(180deg, #1a2636 0%, #121b27 100%); }
    body.theme-violet { --bg: #f5f2ff; --panel: #ffffff; --panel-soft: #faf7ff; --text: #241f3d; --muted: #746e92; --line: #ddd4fb; --line-soft: #efe9ff; background: linear-gradient(180deg, #fbf8ff 0%, #f0ebff 100%); }
    body.theme-refinery { --bg: #d7e6fb; --panel: rgba(255,255,255,.32); --panel-soft: rgba(243,248,255,.26); --text: #132236; --muted: #415a77; --line: rgba(176,200,228,.58); --line-soft: rgba(223,234,247,.42); background: linear-gradient(rgba(205,223,246,.16), rgba(208,224,246,.24)), url('/static/theme_refinery.png') center/cover fixed no-repeat; }
    body.theme-refinery .card, body.theme-refinery .metric, body.theme-refinery .search-card, body.theme-refinery .toolbar, body.theme-refinery .train-item, body.theme-refinery .train-field, body.theme-refinery .btn-secondary, body.theme-refinery .btn-ghost, body.theme-refinery .file-label, body.theme-refinery .choice-label, body.theme-refinery .segmented a, body.theme-refinery .quick-link, body.theme-refinery .event-item, body.theme-refinery .notify-item, body.theme-refinery .settings-nav a, body.theme-refinery .field input, body.theme-refinery .field select, body.theme-refinery .field textarea, body.theme-refinery .settings-block, body.theme-refinery .table-card, body.theme-refinery .table-wrap, body.theme-refinery .stop-table-wrap, body.theme-refinery .summary-filter-box, body.theme-refinery .table-wrap table, body.theme-refinery .settings-table, body.theme-refinery .events-card, body.theme-refinery .map-card { background-color: rgba(255,255,255,.30); backdrop-filter: blur(6px); }
    body.theme-refinery thead th, body.theme-refinery .selection-table thead th, body.theme-refinery .stop-table thead th, body.theme-refinery .manual-table thead th, body.theme-refinery .detail-table thead th { background: rgba(231,240,252,.40); backdrop-filter: blur(8px); }
    body.theme-refinery tbody td, body.theme-refinery .settings-table td { background: rgba(255,255,255,.18); }
    body.theme-refinery tbody tr:nth-child(even) td { background: rgba(246,250,255,.12); }
    body.accent-global { }
    body.radius-compact { --radius: 6px; }
    body.radius-medium { --radius: 8px; }
    body.radius-soft { --radius: 10px; }
    body.density-compact { font-size: 14px; }
    body.density-compact .shell { padding: 10px; }
    body.density-compact .card { box-shadow: 0 8px 22px rgba(20,37,63,.05); }
    .card { background: var(--panel); border: 1px solid rgba(220,228,238,.95); border-radius: var(--radius); box-shadow: var(--shadow); }

    .main-tabs { display: flex; gap: 8px; margin-bottom: 10px; flex-wrap: wrap; }
    .main-tab {
      display: inline-flex; align-items: center; justify-content: center; min-height: 38px; padding: 0 14px;
      border-radius: 6px; background: #fff; color: #35557b; border: 1px solid var(--line); text-decoration: none;
      font-size: 13px; font-weight: 800; letter-spacing: -.01em; transition: background .12s ease, border-color .12s ease, color .12s ease, transform .12s ease;
    }
    .main-tab:hover { transform: translateY(-1px); }
    .main-tab-settings { margin-left: auto; }
    .main-tab.is-active { background: var(--accent-soft); color: var(--accent); border-color: {{ ui_preferences.accent_border|default("rgba(36,86,212,.24)") }}; }
    .sub-tabs { display:flex; gap:8px; margin: -2px 0 10px 0; flex-wrap: wrap; }
    .sub-tab { display:inline-flex; align-items:center; min-height: 32px; padding: 0 12px; border-radius: 7px; border:1px solid var(--line); background:#fff; color: var(--text); text-decoration:none; font-size:12px; font-weight:700; }
    .sub-tab.is-active { background: var(--accent-soft); color: var(--accent); border-color: {{ ui_preferences.accent_border|default("rgba(36,86,212,.24)") }}; }

    .topbar { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 8px 10px; margin-bottom: 10px; }
    .topbar-left { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
    .title { font-size: 18px; font-weight: 800; letter-spacing: -.03em; line-height: 1.02; }
    .meta { color: var(--muted); font-size: 11px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 760px; }
    .topbar-right { display: flex; align-items: center; justify-content: flex-end; gap: 4px; flex-wrap: wrap; }
    .upload-form { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
    .file-label { display: inline-flex; align-items: center; gap: 6px; min-height: 31px; padding: 0 9px; border-radius: 7px; border: 1px dashed #c4d3e5; background: #fbfdff; color: var(--accent); font-size: 12px; font-weight: 600; cursor: pointer; white-space: nowrap; }
    .file-label input { display: none; }
    .choice-label { border-style: solid; background: #fff; }
    .choice-label.is-checked { background: var(--accent-soft); color: var(--accent); border-color: {{ ui_preferences.accent_border|default("rgba(36,86,212,.24)") }}; box-shadow: inset 0 0 0 1px {{ ui_preferences.accent_soft|default("rgba(36,86,212,.12)") }}; }
    .choice-label.is-checked span { color: var(--accent); }
    .btn { display: inline-flex; align-items: center; justify-content: center; min-height: 28px; padding: 0 8px; border-radius: 6px; border: 1px solid transparent; font-weight: 700; font-size: 11px; text-decoration: none; cursor: pointer; transition: background .12s ease, border-color .12s ease, color .12s ease, transform .12s ease; white-space: nowrap; color: inherit; background: transparent; }
    .btn:hover { transform: translateY(-1px); }
    .btn-primary { background: var(--accent); color: white; border-color: var(--accent); }
    .btn-secondary { background: white; color: var(--accent); border-color: var(--line); }
    .btn-soft { background: var(--accent-soft); color: var(--accent); border-color: {{ ui_preferences.accent_soft|default("rgba(36,86,212,.12)") }}; }
    .btn-ghost { background: #fff; color: #4b6380; border-color: var(--line); }

    .error, .success { padding: 10px 12px; margin-bottom: 12px; border-radius: 6px; font-size: 13px; font-weight: 700; }
    .error { background: #fff6f6; border: 1px solid #f2caca; color: #9c3030; transition: opacity .28s ease, transform .28s ease, margin .28s ease, padding .28s ease, max-height .28s ease; max-height: 240px; overflow: hidden; }
    .error.is-hiding { opacity: 0; transform: translateY(-6px); margin-top: 0; margin-bottom: 0; padding-top: 0; padding-bottom: 0; border-width: 0; max-height: 0; }
    .success { background: #f4fbf6; border: 1px solid #c9ebd1; color: #247545; }

    .header-grid { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; align-items: stretch; }
    .header-grid.header-grid-approach, .header-grid.header-grid-departure { display: flex; flex-wrap: wrap; }

    .metric { padding: 7px 8px; background: linear-gradient(180deg, #ffffff 0%, #fbfdff 100%); min-height: 66px; flex: 1 1 145px; min-width: 145px; max-width: 210px; }
    .header-grid.header-grid-approach .metric,
    .header-grid.header-grid-departure .metric { flex: 1 1 126px; min-width: 126px; max-width: 170px; }
    .metric .label { color: var(--muted); font-size: 10px; margin-bottom: 4px; text-transform: uppercase; letter-spacing: .05em; }
    .metric .value { font-size: 16px; font-weight: 800; letter-spacing: -.03em; line-height: 1.1; }
    .metric .sub { margin-top: 3px; color: var(--muted); font-size: 10px; line-height: 1.25; }
    .metric-link { display: block; color: inherit; text-decoration: none; transition: transform .12s ease, box-shadow .12s ease, border-color .12s ease; }
    .metric-link:hover { transform: translateY(-1px); box-shadow: 0 12px 28px rgba(20, 37, 63, .08); border-color: #cfe0ff; }
    .metric-link .value { color: var(--accent); }
    .metric-danger { background: linear-gradient(180deg, #ffffff 0%, var(--danger-soft) 100%); border-color: var(--danger-border); }
    .metric-danger .value, .metric-link.metric-danger .value { color: var(--danger); }

    .search-card { padding: 7px 8px; min-height: 66px; display: flex; flex-direction: column; justify-content: center; background: linear-gradient(180deg, #ffffff 0%, #fbfdff 100%); flex: 1 1 290px; min-width: 290px; max-width: 560px; }
    .header-grid.header-grid-approach .search-card,
    .header-grid.header-grid-departure .search-card { flex: 1 1 250px; min-width: 250px; max-width: 340px; }
    .search-form { display: flex; align-items: center; gap: 8px; width: 100%; }
    .search-input { flex: 1; min-width: 0; height: 34px; padding: 0 11px; border-radius: 7px; border: 1px solid var(--line); background: #fff; color: var(--text); font-size: 13px; outline: none; }
    .search-input:focus { border-color: #bcd1ff; box-shadow: 0 0 0 3px {{ ui_preferences.accent_focus|default("rgba(36,86,212,.16)") }}; }
    .search-caption { color: var(--muted); font-size: 10px; margin-bottom: 6px; text-transform: uppercase; letter-spacing: .05em; font-weight: 700; }

    .table-card { overflow: hidden; }
    .toolbar { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 9px 11px; border-bottom: 1px solid var(--line-soft); background: var(--panel-soft); }
    .toolbar-title { font-size: 13px; font-weight: 800; letter-spacing: -.02em; }
    .toolbar-sub { color: var(--muted); font-size: 11px; margin-top: 2px; }
    .toolbar-right { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
    .badge { display: inline-flex; align-items: center; min-height: 24px; padding: 0 8px; border-radius: 999px; background: white; color: var(--accent); border: 1px solid var(--line); font-size: 11px; font-weight: 700; white-space: nowrap; }

    .table-wrap { overflow-x: auto; overflow-y: auto; max-height: calc(100vh - 290px); }
    table { width: 100%; border-collapse: separate; border-spacing: 0; table-layout: fixed; }
    .summary-table { width: 100%; }
    .detail-table { table-layout: auto; min-width: 1780px; }
    .detail-table th, .detail-table td { white-space: nowrap; }

    .detail-col-wagon { width: 110px; }
    .detail-col-group { width: 84px; }
    .detail-col-kind { width: 180px; }
    .detail-col-station { width: 180px; }
    .detail-col-road { width: 170px; }
    .detail-col-dest { width: 170px; }
    .detail-col-op { width: 170px; }
    .detail-col-date { width: 190px; }
    .detail-col-weight { width: 140px; }
    .detail-col-origin { width: 180px; }
    .detail-col-train { width: 250px; }
    .detail-col-dist { width: 150px; }
    .detail-col-norm { width: 170px; }

    thead th { position: sticky; z-index: 5; background: rgba(248,251,255,.985); color: #3c5b7f; font-size: 11px; text-transform: uppercase; letter-spacing: .06em; padding: 8px 7px; border-bottom: 1px solid var(--line); box-shadow: 0 1px 0 var(--line); white-space: nowrap; }
    .summary-table thead tr:first-child th { top: 0; }
    .summary-table thead tr:nth-child(2) th { top: 33px; }
    .detail-table thead th { top: 0; }
    .summary-table thead th.group-split { border-left: 2px solid var(--group-border); }
    .summary-table thead th.cargo-split { border-left: 1px solid var(--cargo-border); }

    tbody td { padding: 5px 7px; border-bottom: 1px solid var(--line-soft); font-size: 13px; white-space: nowrap; line-height: 1.15; }
    tbody tr:last-child td { border-bottom: 0; }
    .c-name { width: 28%; min-width: 220px; white-space: normal; }
    .num-col { width: 5.5%; min-width: 56px; }
    .raw-material-table thead th { white-space: normal; word-break: break-word; overflow-wrap: anywhere; line-height: 1.15; text-align: center; }
    .raw-material-table .c-name.raw-material-interval-col { width: 160px; min-width: 160px; max-width: 160px; white-space: nowrap; }
    .raw-material-table .num-col { width: 128px; min-width: 128px; }
    .row-total td { font-weight: 800; background: #f8fbff; }
    .row-road td { background: var(--road); font-weight: 800; padding-top: 4px; padding-bottom: 4px; }
    .row-cargo td { background: #f8fbff; padding-top: 4px; padding-bottom: 4px; }
    .row-cargo td.c-name { padding-left: 34px; color: #30465f; font-weight: 700; }
    .row-station td { background: var(--station); padding-top: 4px; padding-bottom: 4px; }
    .row-station td.c-name { padding-left: 34px; color: #30465f; }
    .row-station.row-nested-bucket td.c-name { padding-left: 58px; }
    .row-cargo.is-collapsed, .row-station.is-collapsed { display: none; }
    .summary-table td.group-split { border-left: 2px solid var(--group-border); }
    .summary-table td.cargo-split { border-left: 1px solid var(--cargo-border); }

    .name-wrap { display: flex; align-items: center; gap: 8px; min-height: 22px; }
    .road-toggle { width: 22px; height: 22px; border-radius: 7px; border: 1px solid #d6e2f1; background: #fff; color: #2d538b; display: inline-flex; align-items: center; justify-content: center; cursor: pointer; font-size: 11px; font-weight: 900; line-height: 1; flex: 0 0 22px; transition: background .12s ease, border-color .12s ease, transform .12s ease; }
    .road-toggle:hover { background: var(--accent-soft); border-color: {{ ui_preferences.accent_border|default("rgba(36,86,212,.24)") }}; }
    .road-toggle.is-collapsed { transform: rotate(-90deg); }
    .road-placeholder { width: 22px; flex: 0 0 22px; display: inline-block; }
    td.num { text-align: center; font-variant-numeric: tabular-nums; padding: 2px 4px; }

    .cell-link { display: inline-flex; align-items: center; justify-content: center; width: 100%; min-height: 22px; padding: 0 6px; border-radius: 6px; text-decoration: none; color: #1f4cc3; font-weight: 800; transition: background .12s ease, color .12s ease, box-shadow .12s ease; }
    .cell-link:hover { background: var(--accent-soft); color: var(--accent); box-shadow: inset 0 0 0 1px {{ ui_preferences.accent_soft|default("rgba(36,86,212,.12)") }}; }

    .summary-row-main { display:flex; align-items:center; gap:8px; width:100%; min-width:0; }
    .summary-row-label { min-width:0; flex:1 1 auto; white-space:normal; word-break:break-word; }
    .summary-row-link { min-width:0; flex:1 1 auto; white-space:normal; word-break:break-word; color:inherit; text-decoration:none; border-radius:8px; padding:2px 4px; margin:-2px -4px; transition: color .12s ease, background .12s ease; }
    .summary-row-link:hover { color:var(--accent); background:var(--accent-soft); }
    .cell-empty { display: inline-flex; align-items: center; justify-content: center; width: 100%; min-height: 22px; color: #b2bfce; }

    .breadcrumb { display: inline-flex; gap: 8px; align-items: center; flex-wrap: wrap; padding: 8px 12px; border-radius: 999px; background: #f8fbff; border: 1px solid var(--line); color: var(--muted); font-size: 12px; margin-bottom: 10px; }
    .breadcrumb a { color: var(--accent); text-decoration: none; font-weight: 700; }

    .detail-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; padding: 10px 12px; margin-bottom: 12px; }
    .detail-title { font-size: 17px; font-weight: 800; letter-spacing: -.02em; margin: 0; }
    .chips { display: flex; gap: 8px; flex-wrap: wrap; }
    .chip { display: inline-flex; align-items: center; min-height: 28px; padding: 0 10px; border-radius: 999px; background: var(--accent-soft); color: var(--accent); font-size: 12px; font-weight: 700; }
    .mono { font-family: var(--mono); }
    .empty { padding: 28px; text-align: center; color: var(--muted); font-size: 13px; }

    .th-wrap { display: grid; grid-template-columns: minmax(74px, 1fr) 20px; align-items: start; gap: 8px; }
    .th-wrap > span { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; line-height: 1.15; min-height: calc(1.15em * 2); }
    .col-filter-btn { display: inline-flex; align-items: center; justify-content: center; width: 20px; height: 20px; border-radius: 6px; border: 1px solid #d6e2f1; background: #fff; color: #2d538b; font-size: 11px; cursor: pointer; padding: 0; flex: 0 0 20px; }
    .col-filter-btn.is-active { background: var(--accent-soft); border-color: {{ ui_preferences.accent_border|default("rgba(36,86,212,.24)") }}; color: var(--accent); }
    .filter-popover { position: fixed; z-index: 1000; width: 320px; max-height: 360px; overflow: auto; background: #fff; border: 1px solid var(--line); border-radius: 6px; box-shadow: 0 18px 44px rgba(20,37,63,.15); padding: 10px; }
    .filter-actions { display: flex; gap: 8px; margin-bottom: 10px; flex-wrap: wrap; }
    .filter-actions button { border: 1px solid var(--line); background: #fff; color: #35557b; border-radius: 6px; min-height: 28px; padding: 0 10px; cursor: pointer; font-size: 12px; font-weight: 700; }
    .filter-list { display: grid; gap: 6px; }
    .filter-item { display: flex; align-items: flex-start; gap: 8px; font-size: 12px; color: #30465f; line-height: 1.25; }
    .filter-empty { color: var(--muted); font-size: 12px; padding: 6px 0; }

    .train-board { padding: 12px; margin-bottom: 12px; }
    .train-board-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 10px; }
    .train-item { border: 1px solid var(--line); border-radius: 14px; background: linear-gradient(180deg, #fff 0%, #fbfdff 100%); padding: 12px; overflow-wrap: anywhere; }
    .train-item-head { display: flex; justify-content: space-between; gap: 10px; align-items: flex-start; margin-bottom: 10px; }
    .train-item-title { font-size: 14px; font-weight: 800; line-height: 1.2; word-break: break-word; }
    .train-item-sub { color: var(--muted); font-size: 11px; margin-top: 4px; line-height: 1.25; }
    .train-item-badge { min-width: 56px; text-align: center; padding: 6px 8px; border-radius: 6px; background: var(--accent-soft); color: var(--accent); font-size: 11px; font-weight: 800; }
    .train-item-badge-link { text-decoration: none; display: inline-flex; align-items: center; justify-content: center; }
    .train-item-badge-link:hover { background: #dfeaff; }
    .train-progress { margin-bottom: 10px; }
    .train-progress-meta { display: flex; justify-content: space-between; gap: 8px; font-size: 11px; color: var(--muted); margin-bottom: 6px; }
    .train-progress-bar { height: 12px; border-radius: 999px; background: #edf2f7; overflow: hidden; }
    .train-progress-fill { height: 100%; border-radius: 999px; }
    .progress-low { background: var(--progress-low); }
    .progress-mid { background: var(--progress-mid); }
    .progress-high { background: var(--progress-high); }
    .train-fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
    .train-field { border: 1px solid #eef3f8; border-radius: 7px; padding: 8px; background: #fff; min-height: 58px; }
    .train-field-label { color: var(--muted); font-size: 10px; text-transform: uppercase; letter-spacing: .04em; line-height: 1.25; margin-bottom: 4px; white-space: normal; }
    .train-field-value { font-size: 12px; font-weight: 700; line-height: 1.25; white-space: normal; word-break: break-word; }


    .activation-layout { display: grid; grid-template-columns: minmax(320px, 1.05fr) minmax(320px, 1fr); gap: 12px; margin-bottom: 12px; }
    .activation-card { padding: 16px; }
    .activation-title { font-size: 20px; font-weight: 800; letter-spacing: -.03em; margin: 0 0 6px 0; }
    .activation-sub { color: var(--muted); font-size: 13px; line-height: 1.45; margin-bottom: 12px; }
    .activation-grid { display: grid; grid-template-columns: 1fr; gap: 10px; }
    .activation-box { border: 1px solid var(--line-soft); border-radius: 14px; background: linear-gradient(180deg, #fff 0%, #fbfdff 100%); padding: 12px; }
    .activation-box-title { font-size: 12px; font-weight: 800; letter-spacing: .02em; text-transform: uppercase; color: #4a6282; margin-bottom: 6px; }
    .activation-code { font-family: var(--mono); font-size: 24px; font-weight: 800; letter-spacing: .08em; line-height: 1.2; word-break: break-word; }
    .activation-kv { display: grid; gap: 8px; margin-top: 8px; }
    .activation-kv-row { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; border-top: 1px dashed #e8eef6; padding-top: 8px; }
    .activation-kv-label { color: var(--muted); font-size: 12px; }
    .activation-kv-value { font-size: 12px; font-weight: 700; text-align: right; word-break: break-word; }
    .license-status { display: inline-flex; align-items: center; min-height: 30px; padding: 0 12px; border-radius: 999px; font-size: 12px; font-weight: 800; }
    .license-status.ok { background: #eef9f1; color: #237245; border: 1px solid #cce8d4; }
    .license-status.bad { background: #fff2f2; color: #a33636; border: 1px solid #efcaca; }
    .license-status.warn { background: #fff9ef; color: #9a6418; border: 1px solid #f1ddba; }
    .activation-actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px; }
    .activation-form { display: grid; gap: 10px; margin-top: 10px; }
    .activation-help { color: var(--muted); font-size: 12px; line-height: 1.45; }
    .update-box { border-left: 4px solid {{ ui_preferences.accent_border|default("rgba(36,86,212,.24)") }}; padding-left: 12px; }
    .update-list { margin: 8px 0 0 0; padding-left: 18px; color: var(--accent); font-size: 12px; line-height: 1.45; }
    .mini-note { font-size: 11px; color: var(--muted); line-height: 1.45; margin-top: 8px; }

    .dashboard-shell { display:grid; grid-template-columns: 248px minmax(0, 1fr); gap: 12px; margin-bottom: 12px; align-items:start; }
    .dashboard-shell.dashboard-fixed { min-height: calc(100vh - 118px); height: auto; overflow: visible; align-items: stretch; }
    .dashboard-main { display:grid; grid-template-rows:auto minmax(0, 1fr); gap:12px; min-width:0; min-height:0; height:auto; }
    .dashboard-side { display:grid; gap:8px; align-content:start; min-height:0; height:auto; }
    .dashboard-side .side-card { min-height: 0; height:auto; display:grid; grid-template-rows:auto 1fr; background: transparent; border: 0; box-shadow:none; padding:0; }
    .dashboard-side .quick-links { align-content:start; height:auto; gap:6px; overflow:visible; }
    .dashboard-hero { padding: 14px; }
    .dashboard-hero-head { display:flex; justify-content:space-between; gap:12px; align-items:flex-start; margin-bottom: 12px; }
    .dashboard-hero-title { font-size: 24px; font-weight: 500; letter-spacing: -.02em; margin:0; }
    .dashboard-hero-sub { color: var(--muted); font-size: 12px; line-height: 1.4; margin-top: 4px; }
    .dashboard-actions { display:flex; flex-wrap:wrap; gap:8px; justify-content:flex-end; }
    .dashboard-metrics { display:grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 10px; }
    .dash-metric { padding: 12px; min-height: 88px; }
    .dash-metric-label { color: var(--muted); font-size: 11px; font-weight:600; text-transform: uppercase; letter-spacing: .04em; margin-bottom: 8px; line-height:1.25; }
    .dash-metric-value { font-size: 28px; font-weight: 700; letter-spacing: -.03em; line-height: 1; }
    .dash-metric-foot { margin-top: 10px; display:flex; justify-content:flex-end; gap:10px; align-items:flex-end; }
    .dash-metric-trend { font-size: 12px; font-weight: 800; white-space: nowrap; color: var(--danger) !important; }
    .dash-metric-trend.up { color: var(--danger) !important; }
    .dash-metric-trend.down { color: var(--danger) !important; }
    .dash-metric-trend.flat { color: var(--danger) !important; }
    .dashboard-grid-2 { display:grid; grid-template-columns: minmax(0, 1.55fr) minmax(360px, .82fr); gap:12px; min-height:0; height:auto; align-items:stretch; }
    .map-card, .events-card, .side-card { padding: 12px; min-height:0; }
    .map-card { display:flex; flex-direction:column; height:100%; }
    .section-title { font-size: 15px; font-weight: 700; letter-spacing: -.01em; margin:0; }
    .section-sub { color: var(--muted); font-size: 11px; margin-top: 4px; line-height: 1.35; }
    .map-head { display:flex; justify-content:space-between; gap:10px; align-items:center; margin-bottom: 10px; }
    .segmented { display:inline-flex; gap:6px; flex-wrap:nowrap; white-space:nowrap; }
    .segmented a { text-decoration:none; min-height: 28px; padding: 0 10px; border:1px solid var(--line); color:var(--accent); background:#fff; display:inline-flex; align-items:center; font-size:12px; font-weight:700; border-radius: 7px; }
    .segmented a.is-active { background: var(--accent-soft); color: var(--accent); border-color:{{ ui_preferences.accent_border|default("rgba(36,86,212,.24)") }}; }
    .map-card { display:grid; grid-template-rows:auto minmax(0, 1fr) auto; min-height:0; }
    .map-stage { position:relative; overflow:hidden; min-height: clamp(320px, 46vh, 640px); height: 100%; border:1px solid var(--line-soft); background: linear-gradient(180deg, rgba(223,236,252,.96) 0%, rgba(240,247,255,.97) 100%); border-radius: 8px; }
    .map-stage::before { content:''; position:absolute; inset:0; background: radial-gradient(circle at 28% 34%, rgba(89,139,214,.18), transparent 34%), radial-gradient(circle at 64% 56%, rgba(89,139,214,.14), transparent 40%); }
    .map-stage::after { content:''; position:absolute; inset:0; background-image: linear-gradient(rgba(125,156,194,.05) 1px, transparent 1px), linear-gradient(90deg, rgba(125,156,194,.05) 1px, transparent 1px); background-size: 56px 56px; opacity:.18; }
    .map-outline { position:absolute; inset:12px; border:1px dashed rgba(86,112,148,.12); border-radius: 12px; }
    .map-base-image { display:block; position:absolute; inset:14px 16px 16px 16px; width:calc(100% - 32px); height:calc(100% - 30px); object-fit:contain; z-index:1; opacity:.98; filter: saturate(1.16) contrast(1.07); }
    .map-svg { display:none; }
    .map-point { position:absolute; z-index:3; transform: translate(-50%, -50%); min-width: 18px; height:18px; border-radius: 999px; background: rgba(36,86,212,.15); border:1px solid rgba(36,86,212,.25); display:flex; align-items:center; justify-content:center; box-shadow: 0 10px 24px rgba(36,86,212,.12); }
    .map-point-dot { width:10px; height:10px; border-radius:999px; background: var(--accent); }
    .map-point.is-empty .map-point-dot { background:#7b8ea8; }
    .map-point-badge { position:absolute; top:-8px; right:-8px; min-width:20px; height:20px; padding:0 5px; border-radius:999px; background:#fff; border:1px solid var(--line); color:var(--accent); display:flex; align-items:center; justify-content:center; font-size:10px; font-weight:700; }
    .map-legend { display:flex; gap:12px; flex-wrap:wrap; margin-top: 10px; color:var(--accent); font-size:12px; }
    .legend-item { display:inline-flex; align-items:center; gap:6px; }
    .legend-dot { width:10px; height:10px; border-radius:999px; background:var(--accent); }
    .legend-dot.empty { background:#7b8ea8; width:10px; height:10px; flex:0 0 10px; }
    .events-card { display:flex; flex-direction:column; min-height:0; height:100%; align-self:stretch; }
    .events-list, .quick-links, .notify-list, .settings-nav { display:grid; gap:8px; margin-top: 10px; }
    .events-list { flex:1 1 auto; min-height:0; max-height:none; overflow:auto; }
    .hero-photo-stage { flex:1 1 auto; }
    .events-list { min-height:0; max-height: calc(clamp(280px, 46vh, 640px) + 130px); overflow-y:auto; overflow-x:hidden; padding-right: 4px; }
    .event-item, .quick-link, .notify-item, .settings-nav a { border:1px solid var(--line-soft); background:#fff; border-radius: 8px; padding: 10px; }
    .dashboard-side .section-title { margin: 0 0 6px 0; }
    .dashboard-side .quick-links { margin-top: 0; }
    .dashboard-side .quick-link { background: rgba(255,255,255,.16); backdrop-filter: blur(4px); border-color: rgba(216,226,240,.72); }
    .event-item { display:grid; gap:5px; align-content:start; }
    .event-top { display:grid; grid-template-columns:minmax(0,1fr); gap:4px; align-items:flex-start; }
    .event-title { font-size: 13px; font-weight: 600; line-height:1.35; word-break:break-word; white-space:normal; }
    .event-time { color: var(--muted); font-size: 11px; white-space: normal; line-height:1.35; }
    .event-meta { color: var(--accent); font-size: 11px; line-height: 1.35; word-break:break-word; }
    .events-list .empty { padding: 14px 10px; }
    .quick-links { max-height:none; overflow:visible; padding-right: 0; }
    .quick-link { text-decoration:none; color:inherit; display:flex; justify-content:space-between; gap:10px; align-items:center; transition: transform .12s ease, border-color .12s ease; }
    .quick-link:hover { transform: translateY(-1px); border-color:#c6d8f8; }
    .quick-link-title { font-size: 12px; font-weight: 700; }
    .quick-link-sub { color: var(--muted); font-size: 10px; margin-top: 2px; }
    .dashboard-side .quick-link { padding: 8px 10px; min-height: 0; }
    .dashboard-side .quick-link-sub { display:none; }
    .station-quick-select { display:block; }
    .station-quick-select summary { list-style:none; cursor:pointer; }
    .station-quick-select summary::-webkit-details-marker { display:none; }
    .station-quick-select[open] .station-quick-summary { border-bottom-left-radius: 6px; border-bottom-right-radius: 6px; }
    .station-quick-current { margin-top:2px; font-size:10px; color:var(--muted); line-height:1.2; }
    .station-quick-form { display:grid; gap:6px; padding: 8px 9px 9px; margin-top: 4px; border:1px solid var(--line-soft); border-radius:8px; background:rgba(255,255,255,.52); }
    .station-quick-dropdown { width:100%; min-height:30px; border:1px solid var(--line); border-radius:7px; background:#fff; color:var(--text); padding:5px 8px; font-size:12px; }
    .station-quick-clear { font-size:11px; font-weight:700; color:var(--accent); text-decoration:none; }
    .station-quick-clear:hover { text-decoration:underline; }
    .map-tools { display:flex; align-items:center; gap:8px; flex-wrap:nowrap; }
    .map-refresh-btn { width:30px; height:30px; display:inline-flex; align-items:center; justify-content:center; border-radius:8px; border:1px solid var(--line); background:#fff; color:var(--accent); cursor:pointer; box-shadow: var(--shadow); font-size:16px; line-height:1; }
    .map-refresh-btn:hover { background: var(--accent-soft); border-color: {{ ui_preferences.accent_border|default("rgba(36,86,212,.24)") }}; }
    .map-refresh-btn svg { width:16px; height:16px; }
    .hero-photo-stage { position:relative; min-height: clamp(420px, 58vh, 760px); border:1px solid var(--line-soft); border-radius: 12px; overflow:hidden; background: linear-gradient(180deg, rgba(223,236,252,.50) 0%, rgba(240,247,255,.40) 100%); }
    .hero-photo-stage img { display:block; width:100%; height:100%; object-fit:cover; object-position:center; }
    .hero-photo-overlay { position:absolute; inset:0; background: linear-gradient(180deg, rgba(255,255,255,.06) 0%, rgba(255,255,255,.02) 100%); pointer-events:none; }
    .map-stage.is-refreshing .map-point { opacity:.35; }
    .quick-link-arrow { color: var(--accent); font-size: 18px; font-weight: 600; }
    .settings-shell { display:grid; grid-template-columns: 260px minmax(0, 1fr); gap:12px; margin-bottom:12px; }
    .settings-card { padding: 14px; }
    .settings-block { border:1px solid var(--line-soft); border-radius: 8px; padding:12px; background: linear-gradient(180deg, #fff 0%, #fbfdff 100%); margin-top: 10px; scroll-margin-top: 12px; }
    .settings-block:first-child { margin-top:0; }
    .settings-block-title { font-size:14px; font-weight:800; margin:0 0 8px 0; }
    .settings-grid-form { display:grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap:10px; }
    .field { display:grid; gap:5px; }
    .field label { font-size:11px; font-weight:700; color:var(--accent); text-transform: uppercase; letter-spacing:.04em; }
    .field input, .field select, .field textarea { width:100%; min-height:34px; border:1px solid var(--line); border-radius: 7px; background:#fff; color:var(--text); padding: 7px 10px; font: inherit; }
    .field textarea { min-height:74px; resize: vertical; }
    .field-check { display:flex; align-items:center; gap:8px; padding-top: 26px; }
    .field-check input { width:16px; height:16px; }
    .settings-table { width:100%; border-collapse: separate; border-spacing:0; }
    .settings-table th, .settings-table td { padding: 9px 8px; border-bottom:1px solid var(--line-soft); font-size:12px; text-align:left; vertical-align:top; }
    .settings-table th { color:var(--accent); font-size:11px; text-transform: uppercase; letter-spacing:.05em; }
    .pill { display:inline-flex; align-items:center; min-height:22px; padding:0 8px; border-radius:999px; background:var(--accent-soft); color:var(--accent); font-size:11px; font-weight:700; }

    .main-tab, .sub-tab, .file-label, .btn-secondary, .badge, .segmented a, .event-meta, .quick-link-title, .quick-link-sub, .section-sub, .field label, .settings-table th, .map-legend, .map-point-badge, .update-list { color: var(--accent); }
    .station-link, .stop-group-link, .filter-actions button, .breadcrumb a, .choice-label.is-checked span, .col-filter-btn.is-active, .quick-link-arrow { color: var(--accent); }
    body.accent-global .title, body.accent-global .meta, body.accent-global .toolbar-title, body.accent-global .toolbar-meta, body.accent-global .table-wrap, body.accent-global tbody td, body.accent-global thead th, body.accent-global .dash-metric-label, body.accent-global .dash-metric-value, body.accent-global .dash-metric-trend, body.accent-global .event-title, body.accent-global .event-time, body.accent-global .loading-title, body.accent-global .loading-sub { color: var(--accent); }
    body.accent-global .metric-danger .value, body.accent-global .metric-danger .label, body.accent-global .metric-danger .sub, body.accent-global .error, body.accent-global .danger-text, body.accent-global [data-ugle-color='danger'] { color: var(--danger) !important; }
    @media (max-width: 1200px) { .dashboard-shell, .settings-shell, .dashboard-grid-2 { grid-template-columns:1fr; } .dashboard-shell.dashboard-fixed { height:auto; overflow:visible; } .dashboard-metrics { grid-template-columns: repeat(3, minmax(0, 1fr)); } .quick-links, .events-list { max-height:none; overflow:visible; } }
    @media (max-width: 760px) { .dashboard-metrics, .settings-grid-form { grid-template-columns:1fr; } .dashboard-hero-head, .map-head { flex-direction:column; } .segmented { flex-wrap:wrap; } .events-card { margin-top: 0; } }

    @media (max-width: 1280px) {
      .header-grid.header-grid-approach, .header-grid.header-grid-departure { display: flex; flex-wrap: wrap; }
      .search-card { flex-basis: 100%; max-width: none; }
      .metric { min-width: 160px; max-width: none; }
    }
    @media (max-width: 1100px) {
      .activation-layout { grid-template-columns: 1fr; }

      .topbar { flex-direction: column; align-items: stretch; }
      .topbar-right { justify-content: flex-start; }
      .meta { max-width: none; }
      .header-grid.header-grid-approach, .header-grid.header-grid-departure { grid-template-columns: repeat(2, minmax(180px, 1fr)); }
      .table-wrap { max-height: calc(100vh - 330px); }
      .train-fields { grid-template-columns: 1fr; }
    }
    @media (max-width: 760px) {
      .shell { padding: 10px; }
      .title { font-size: 17px; }
      .toolbar { flex-direction: column; align-items: flex-start; }
      .toolbar-right { width: 100%; }
      .upload-form { width: 100%; }
      .search-form { flex-direction: column; align-items: stretch; }
      .table-wrap { max-height: calc(100vh - 390px); }
      .train-board-grid { grid-template-columns: 1fr; }
      .train-item-head { flex-direction: column; }
    }

    .archive-form { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
    .archive-date { height: 31px; padding: 0 8px; border-radius: 7px; border: 1px solid var(--line); background: #fff; color: var(--text); font-size: 12px; }
    .detail-table { table-layout: auto; min-width: 2580px; font-family: "Times New Roman", Times, serif; font-size: 10pt; }
    .detail-table th, .detail-table td { white-space: normal; vertical-align: top; border-right: 1px solid var(--line-soft); }
    .detail-table th:last-child, .detail-table td:last-child { border-right: 0; }

    .technical-state-wrap { max-height: calc(100vh - 320px); }
    .technical-state-table { min-width: 0; width: max-content; table-layout: auto; }
    .technical-state-table th, .technical-state-table td { white-space: nowrap; }
    .technical-state-table thead th { min-width: 64px; }
    .technical-state-table th:nth-child(1), .technical-state-table td:nth-child(1) { width: 104px; min-width: 104px; }
    .technical-state-table th:nth-child(2), .technical-state-table td:nth-child(2) { width: 124px; min-width: 124px; }
    .technical-state-table th:nth-child(3), .technical-state-table td:nth-child(3) { width: 250px; min-width: 250px; }
    .technical-state-table th:nth-child(4), .technical-state-table td:nth-child(4) { width: 250px; min-width: 250px; }
    .technical-state-table th:nth-child(5), .technical-state-table td:nth-child(5) { width: 420px; min-width: 420px; }
    .technical-state-table th:nth-child(6), .technical-state-table td:nth-child(6) { width: 320px; min-width: 320px; }
    .detail-table thead th { text-transform: none; letter-spacing: 0; font-size: 11px; line-height: 1.15; white-space: normal; word-break: keep-all; overflow-wrap: anywhere; min-width: 92px; }
    .detail-col-owner { width: 210px; }
    .detail-col-wagon { width: 110px; }
    .detail-col-kind { width: 170px; }
    .detail-col-cargo { width: 240px; }
    .detail-col-weight { width: 100px; }
    .detail-col-origin-st { width: 150px; }
    .detail-col-origin-rd { width: 150px; }
    .detail-col-dest { width: 175px; }
    .detail-col-station { width: 170px; }
    .detail-col-road { width: 165px; }
    .detail-col-op { width: 235px; }
    .detail-col-train { width: 280px; }
    .detail-col-date { width: 185px; }
    .detail-col-state { width: 135px; }
    .detail-col-dist { width: 118px; }
    .detail-col-norm { width: 145px; }
    .detail-col-arrival { width: 185px; }
    .station-picker { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 8px; }
    .station-link { display: block; padding: 10px 12px; border-radius: 6px; border: 1px solid var(--line); background: #fff; text-decoration: none; color: var(--accent); font-weight: 700; }
    .station-link:hover { background: var(--accent-soft); border-color: {{ ui_preferences.accent_border|default("rgba(36,86,212,.24)") }}; color: var(--accent); }
    .stop-grid { display: grid; grid-template-columns: 1.1fr 1fr; gap: 12px; }
    .selection-tools { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
    .selection-table { width: 100%; border-collapse: separate; border-spacing: 0; table-layout: fixed; min-width: 760px; }
    .selection-table th, .selection-table td, .stop-table th, .stop-table td { padding: 7px 8px; border-bottom: 1px solid var(--line-soft); font-size: 12px; vertical-align: top; white-space: normal; word-break: break-word; }
    .selection-table thead th, .stop-table thead th { position: sticky; top: 0; background: rgba(248,251,255,.985); z-index: 2; }
    .selection-box { max-height: 520px; overflow: auto; border: 1px solid var(--line); border-radius: 6px; }
    .form-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
    .input { height: 34px; padding: 0 10px; border-radius: 7px; border: 1px solid var(--line); background: #fff; font-size: 13px; }
    .summary-filter-form { margin: 0; }
    .summary-filter-box { display: inline-flex; align-items: center; gap: 10px; padding: 8px 12px; border-radius: 6px; border: 1px solid var(--line); background: var(--panel-soft); color: var(--text); }
    .summary-filter-label { font-size: 12px; font-weight: 700; color: var(--muted); white-space: nowrap; }
    .summary-filter-select { min-width: 320px; max-width: min(560px, 68vw); }
    .approach-top-filters { display:inline-flex; align-items:center; gap:5px; flex-wrap:nowrap; }
    .approach-top-filter { width:154px; max-width:154px; min-height:28px; padding:0 7px; font-size:11px; }
    .approach-top-filter-wide { width:176px; max-width:176px; }
    .approach-filter-reset { min-width:28px; padding:0 7px; }
    .stop-table-wrap { max-height: 520px; overflow: auto; border: 1px solid var(--line); border-radius: 6px; }
    .mini-muted { color: var(--muted); font-size: 12px; }
    .stop-group-list { display: grid; gap: 10px; }
    .stop-group-item { border: 1px solid var(--line); border-radius: 6px; background: #fff; padding: 10px 12px; }
    .stop-group-link { display: flex; align-items: center; justify-content: space-between; gap: 10px; text-decoration: none; color: var(--accent); font-weight: 700; }
    .stop-group-link:hover { color: var(--accent); }
    .stop-group-meta { color: var(--muted); font-size: 11px; margin-top: 4px; }
    .stop-actions { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
    .stop-detail-table { width: 100%; table-layout: fixed; }
    .stop-detail-table th, .stop-detail-table td { padding: 7px 8px; border-bottom: 1px solid var(--line-soft); font-size: 12px; vertical-align: top; white-space: normal; }
    .stop-detail-table .mono { white-space: nowrap; }
    .mailing-table { table-layout: fixed; min-width: 1240px; }
    .mailing-table th, .mailing-table td { white-space: normal; vertical-align: top; word-break: break-word; overflow-wrap: anywhere; line-height: 1.28; }
    .mailing-col-enabled { width: 84px; }
    .mailing-col-name { width: 190px; }
    .mailing-col-report { width: 160px; }
    .mailing-col-recipients { width: 270px; }
    .mailing-col-schedule { width: 170px; }
    .mailing-col-last-run { width: 155px; }
    .mailing-col-status { width: 170px; }
    .mailing-col-actions { width: 250px; }
    .mailing-cell-wrap { display: block; white-space: normal; word-break: break-word; overflow-wrap: anywhere; }
    .manual-layout { display:grid; grid-template-columns: 360px minmax(0, 1fr); gap: 12px; align-items: start; margin-top: 12px; }
    .manual-panel { padding: 12px; }
    .manual-filter-grid { display:grid; gap: 10px; }
    .manual-top-grid { display:grid; grid-template-columns: 1fr 1fr; gap: 8px; }
    .manual-field { display:grid; gap: 6px; }
    .manual-label { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: .05em; font-weight: 700; }
    .manual-select, .manual-text { width: 100%; min-height: 34px; padding: 8px 10px; border-radius: 7px; border: 1px solid var(--line); background: #fff; color: var(--text); font-size: 13px; }
    .manual-select[multiple] { min-height: 120px; }
    .manual-actions { display:flex; gap: 8px; flex-wrap: wrap; }
    .manual-stats { display:flex; gap: 8px; flex-wrap: wrap; }
    .manual-active { display:flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
    .manual-chip { display:inline-flex; align-items:center; gap: 6px; min-height: 28px; padding: 0 8px 0 10px; border-radius: 999px; background: var(--accent-soft); color: var(--accent); border: 1px solid {{ ui_preferences.accent_soft|default("rgba(36,86,212,.12)") }}; font-size: 11px; font-weight: 700; }
    .manual-chip-remove { display:inline-flex; align-items:center; justify-content:center; width: 18px; height: 18px; border-radius: 999px; text-decoration:none; background: #fff; color: var(--accent); border: 1px solid #c7dafd; font-size: 12px; font-weight: 900; line-height: 1; }
    .manual-chip-remove:hover { background: #e7f0ff; }
    .manual-source-meta { color: var(--muted); font-size: 12px; margin-top: 4px; line-height: 1.4; }
    .manual-empty { padding: 18px 14px; color: var(--muted); }

    .manual-table {
      width: max-content;
      min-width: 0;
      table-layout: auto;
      margin: 0;
    }

    .manual-table thead th {
      position: sticky;
      top: 0;
      z-index: 4;
      background: rgba(248,251,255,.985);
      box-shadow: 0 1px 0 var(--line);
      text-transform: none;
      letter-spacing: 0;
      font-size: 11px;
      line-height: 1.2;
      white-space: normal;
      vertical-align: middle;
      word-break: normal;
      overflow-wrap: normal;
      hyphens: none;
    }

    .manual-table tbody td {
      white-space: normal;
      vertical-align: top;
      word-break: break-word;
      overflow-wrap: anywhere;
      line-height: 1.2;
    }

    .manual-table th[data-manual-col-index],
    .manual-table td[data-manual-col-index] {
      display: table-cell;
    }

    .manual-th-wrap {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 8px;
      min-height: 38px;
    }

    .manual-th-title {
      flex: 1 1 auto;
      min-width: 0;
      word-break: normal;
      overflow-wrap: normal;
      hyphens: none;
    }

    .manual-th-actions {
      display: inline-flex;
      align-items: flex-start;
      gap: 4px;
      flex: 0 0 44px;
    }

    .manual-col-filter-btn,
    .manual-col-hide-btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 20px;
      height: 20px;
      border-radius: 6px;
      border: 1px solid #d6e2f1;
      background: #fff;
      color: #2d538b;
      font-size: 11px;
      cursor: pointer;
      padding: 0;
      flex: 0 0 20px;
    }

    .manual-col-filter-btn.is-active {
      background: var(--accent-soft);
      border-color: {{ ui_preferences.accent_border|default("rgba(36,86,212,.24)") }};
      color: var(--accent);
    }

    .manual-col-hide-btn { color:#8a4b4b; }
    .manual-col-hide-btn:hover { background:#fff3f3; border-color:#efcaca; color:#b23131; }

    .manual-filter-popover {
      position: fixed;
      z-index: 1000;
      width: 320px;
      max-height: 360px;
      overflow: auto;
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 6px;
      box-shadow: 0 18px 44px rgba(20,37,63,.15);
      padding: 10px;
    }

    .manual-filter-actions {
      display: flex;
      gap: 8px;
      margin-bottom: 10px;
      flex-wrap: wrap;
    }

    .manual-filter-actions button {
      border: 1px solid var(--line);
      background: #fff;
      color: #35557b;
      border-radius: 6px;
      min-height: 28px;
      padding: 0 10px;
      cursor: pointer;
      font-size: 12px;
      font-weight: 700;
    }

    .manual-filter-list { display:grid; gap:6px; }
    .manual-filter-item { display:flex; align-items:flex-start; gap:8px; font-size:12px; color:#30465f; line-height:1.25; }
    .manual-filter-empty { color:var(--muted); font-size:12px; padding:6px 0; }

    .manual-col-wagon { width: 110px; }
    .manual-col-kind { width: 150px; }
    .manual-col-state { width: 120px; }
    .manual-col-owner { width: 190px; }
    .manual-col-cargo { width: 220px; }
    .manual-col-shipper { width: 220px; }
    .manual-col-consignee { width: 220px; }
    .manual-col-origin-station { width: 180px; }
    .manual-col-origin-road { width: 170px; }
    .manual-col-destination-station { width: 180px; }
    .manual-col-destination-road { width: 170px; }
    .manual-col-operation-station { width: 180px; }
    .manual-col-operation-road { width: 170px; }
    .manual-col-operation { width: 210px; }
    .manual-col-operation-time { width: 160px; }

    .manual-table .manual-cell-wagon,
    .manual-table .manual-col-wagon {
      white-space:nowrap !important;
      word-break:normal !important;
      overflow-wrap:normal !important;
    }

    .manual-table .manual-cell-wagon { font-variant-numeric: tabular-nums; }
    .manual-table td.is-hidden, .manual-table th.is-hidden { display:none !important; }
    .manual-save-row { display:grid; grid-template-columns: 1fr auto auto auto; gap: 8px; align-items: end; }
    @media (max-width: 1100px) { .manual-layout { grid-template-columns: 1fr; } .manual-top-grid { grid-template-columns: 1fr; } .manual-save-row { grid-template-columns: 1fr 1fr; } }
    .mailing-actions { display:flex; gap:6px; flex-wrap:wrap; align-items:flex-start; }
    .stop-col-check { width: 42px; }
    .stop-col-wagon { width: 105px; }
    .stop-col-kind { width: 120px; }
    .stop-col-op { width: 220px; }
    .stop-col-time { width: 140px; }
    .stop-col-start, .stop-col-end { width: 98px; }
    .stop-col-status { width: 92px; }
    .stop-col-days { width: 65px; }
    .selection-col-check { width: 42px; }
    .selection-col-wagon { width: 105px; }
    .selection-col-kind { width: 120px; }
    .selection-col-op { width: 260px; }
    .selection-col-time { width: 160px; }
    @media (max-width: 1100px) { .stop-grid { grid-template-columns: 1fr; } }

    .loading-overlay {
      position: fixed;
      inset: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 16px;
      background: rgba(244, 247, 251, .28);
      backdrop-filter: blur(2px);
      opacity: 0;
      visibility: hidden;
      pointer-events: none;
      transition: opacity .18s ease, visibility .18s ease;
      z-index: 3000;
    }
    body.is-loading { overflow: hidden; }
    body.is-loading .loading-overlay { opacity: 1; visibility: visible; pointer-events: auto; }
    .loading-panel {
      width: min(360px, calc(100vw - 32px));
      padding: 22px 24px;
      border: 1px solid var(--line);
      border-radius: 10px;
      background: rgba(255,255,255,.92);
      box-shadow: 0 20px 45px rgba(20, 37, 63, .10);
      text-align: center;
    }
    .loading-spinner {
      width: 42px;
      height: 42px;
      margin: 0 auto 14px;
      border-radius: 999px;
      border: 3px solid rgba(109, 129, 154, .18);
      border-top-color: var(--accent);
      animation: loading-spin .8s linear infinite;
    }
    .loading-title {
      font-size: 16px;
      font-weight: 800;
      letter-spacing: -.015em;
      margin-bottom: 6px;
      color: var(--text);
    }
    .loading-sub {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.4;
      margin: 0;
    }
    @keyframes loading-spin {
      from { transform: rotate(0deg); }
      to { transform: rotate(360deg); }
    }

    @media (max-width: 760px) {
      .loading-panel { width: min(100%, calc(100vw - 24px)); padding: 18px 18px; }
      .loading-title { font-size: 15px; }
      .loading-sub { font-size: 11px; }
    }

  </style>
</head>
<body class="theme-{{ ui_preferences.theme|default('light') }} radius-{{ ui_preferences.radius_style|default('soft') }} density-{{ ui_preferences.density|default('standard') }} accent-global">
  <div class="shell">
    {{ body|safe }}
  </div>
  <div class="loading-overlay" id="global-loading-overlay" aria-hidden="true">
    <div class="loading-panel" role="status" aria-live="polite">
      <div class="loading-spinner" aria-hidden="true"></div>
      <div class="loading-title">Загрузка данных, подождите…</div>
      <p class="loading-sub">Выполняется обработка и подготовка данных.</p>
    </div>
  </div>
  <script>
    (function(){
      function hideErrors(){
        var nodes = document.querySelectorAll('.error');
        if(!nodes.length){ return; }
        window.setTimeout(function(){
          nodes.forEach(function(node){
            if(!node || node.dataset.autohideBound === '1'){ return; }
            node.dataset.autohideBound = '1';
            node.classList.add('is-hiding');
            window.setTimeout(function(){ if(node && node.parentNode){ node.parentNode.removeChild(node); } }, 320);
          });
        }, 5000);
      }

      function isExportTarget(value){
        var normalized = (value || '').toLowerCase();
        return normalized.indexOf('/export') !== -1 || normalized.indexOf('/archive/export') !== -1;
      }

      function shouldSkipLoadingForLink(link){
        if(!link){ return true; }
        var href = link.getAttribute('href') || '';
        if(!href || href.charAt(0) === '#' || href.indexOf('javascript:') === 0){ return true; }
        if(link.hasAttribute('download') || link.dataset.noLoading === '1'){ return true; }
        if(link.target && link.target.toLowerCase() === '_blank'){ return true; }
        return isExportTarget(href);
      }

      function shouldSkipLoadingForForm(form){
        if(!form){ return true; }
        if(form.dataset.noLoading === '1'){ return true; }
        var action = form.getAttribute('action') || '';
        return isExportTarget(action);
      }

      function bindGlobalLoading(){
        var overlay = document.getElementById('global-loading-overlay');
        if(!overlay){ return; }
        var timer = null;

        function showLoading(){
          if(timer){ window.clearTimeout(timer); }
          timer = window.setTimeout(function(){
            document.body.classList.add('is-loading');
            overlay.setAttribute('aria-hidden', 'false');
          }, 120);
        }

        function hideLoading(){
          if(timer){
            window.clearTimeout(timer);
            timer = null;
          }
          document.body.classList.remove('is-loading');
          overlay.setAttribute('aria-hidden', 'true');
        }

        document.addEventListener('click', function(event){
          if(event.defaultPrevented){ return; }
          if(event.button !== 0){ return; }
          if(event.metaKey || event.ctrlKey || event.shiftKey || event.altKey){ return; }
          var link = event.target.closest('a[href]');
          if(!link || shouldSkipLoadingForLink(link)){ return; }
          showLoading();
        }, true);

        document.addEventListener('submit', function(event){
          var form = event.target;
          if(!(form instanceof HTMLFormElement) || shouldSkipLoadingForForm(form)){ return; }
          showLoading();
        }, true);

        window.addEventListener('pageshow', hideLoading);
        window.addEventListener('pagehide', hideLoading);
        window.addEventListener('focus', function(){
          if(document.visibilityState === 'visible'){
            hideLoading();
          }
        });
        document.addEventListener('visibilitychange', function(){
          if(document.visibilityState === 'visible'){
            hideLoading();
          }
        });
      }

      function initBaseUi(){
        hideErrors();
        bindGlobalLoading();
      }

      if(document.readyState === 'loading'){
        document.addEventListener('DOMContentLoaded', initBaseUi);
      } else {
        initBaseUi();
      }
    })();
  </script>
</body>
</html>
"""


INDEX_BODY = """
<div class="main-tabs">
  <a class="main-tab {% if current_tab == 'dashboard' %}is-active{% endif %}" href="{{ url_for('index', tab='dashboard') }}">Главный экран</a>
  <a class="main-tab {% if current_tab == 'approach' %}is-active{% endif %}" href="{{ url_for('index', tab='approach') }}">Подход вагонов</a>
  <a class="main-tab {% if current_tab == 'departure' %}is-active{% endif %}" href="{{ url_for('index', tab='departure') }}">Отправление вагонов</a>
  <a class="main-tab {% if current_tab == 'loading' %}is-active{% endif %}" href="{{ url_for('index', tab='loading') }}">Погрузка</a>
  <a class="main-tab {% if current_tab == 'station_idle' %}is-active{% endif %}" href="{{ url_for('index', tab='station_idle') }}">Простои</a>
  <a class="main-tab {% if current_tab == 'raw_material' %}is-active{% endif %}" href="{{ url_for('index', tab='raw_material') }}">Сырье</a>
  <a class="main-tab {% if current_tab == 'technical_state' %}is-active{% endif %}" href="{{ url_for('technical_state_index') }}">Техническое состояние</a>
  <a class="main-tab {% if current_tab == 'manual_filter' %}is-active{% endif %}" href="{{ url_for('index', tab='manual_filter') }}">Ручной фильтр</a>
  <a class="main-tab {% if current_tab == 'archive' %}is-active{% endif %}" href="{{ url_for('archive_search') }}">Архив</a>
  <a class="main-tab {% if current_tab == 'mailing' %}is-active{% endif %}" href="{{ url_for('mailing_rules') }}">Авторассылка справок</a>
  <a class="main-tab main-tab-settings {% if current_tab == 'settings' %}is-active{% endif %}" href="{{ url_for('settings_page') }}">Настройки</a>
</div>

{% if current_tab == 'station_idle' %}
<div class="sub-tabs">
  <a class="sub-tab {% if station_idle_mode == 'ugleuralskaya' %}is-active{% endif %}" href="{{ url_for('index', tab='station_idle', idle_view='ugleuralskaya', archive_date=archive_date) }}">Простой на станции {{ selected_station or destination_keyword or "Углеуральская" }}</a>
  <a class="sub-tab {% if station_idle_mode == 'destination' %}is-active{% endif %}" href="{{ url_for('index', tab='station_idle', idle_view='destination', archive_date=archive_date) }}">Простой на станции назначения</a>
  <a class="sub-tab" href="{{ url_for('claims_ugleuralskaya_index') }}">Претензии на {{ selected_station or destination_keyword or "Углеуральской" }}</a>
</div>
{% endif %}

{% if current_tab == 'loading' %}
<div class="sub-tabs">
  <a class="sub-tab {% if loading_mode == 'today' %}is-active{% endif %}" href="{{ url_for('index', tab='loading', loading_view='today', archive_date=archive_date) }}">Погрузка сегодня</a>
  <a class="sub-tab {% if loading_mode == 'yesterday' %}is-active{% endif %}" href="{{ url_for('index', tab='loading', loading_view='yesterday', archive_date=archive_date) }}">Погрузка вчера</a>
  <a class="sub-tab {% if loading_mode == 'pending' %}is-active{% endif %}" href="{{ url_for('index', tab='loading', loading_view='pending', archive_date=archive_date) }}">Погружены, но не отправлены более суток</a>
  <a class="sub-tab {% if loading_mode == 'month' %}is-active{% endif %}" href="{{ url_for('index', tab='loading', loading_view='month', loading_month=selected_month) }}">Погрузка с начала месяца</a>
</div>
{% endif %}

<section class="card topbar">
  <div class="topbar-left">
    <div class="title">{{ app_title }} — {{ current_tab_label }}</div>
    <div class="meta">
      {{ source_name }}
      {% if source_time %} • {{ source_time }}{% endif %}
      {% if report_date_label %} • Дата справки: {{ report_date_label }}{% endif %}
      {% if archive_date %} • Архив: {{ archive_date }}{% endif %}
    </div>
  </div>

  <div class="topbar-right">
    {% if current_tab == 'approach' %}
    <form class="approach-top-filters" method="get" action="{{ url_for('index') }}">
      <input type="hidden" name="tab" value="approach">
      {% if archive_date %}<input type="hidden" name="archive_date" value="{{ archive_date }}">{% endif %}
      <select class="input approach-top-filter approach-top-filter-wide" name="approach_previous_cargo_filter" title="Ранее выгруженный груз" onchange="this.form.submit()">
        <option value="">Ранее выгруженный груз</option>
        {% for option in approach_previous_cargo_filter_options %}
          <option value="{{ option }}" {% if option == approach_previous_cargo_filter_value %}selected{% endif %}>{{ option }}</option>
        {% endfor %}
      </select>
      <select class="input approach-top-filter" name="approach_cargo_filter" title="Груз" onchange="this.form.submit()">
        <option value="">Груз</option>
        {% for option in approach_cargo_filter_options %}
          <option value="{{ option }}" {% if option == approach_cargo_filter_value %}selected{% endif %}>{{ option }}</option>
        {% endfor %}
      </select>
      {% if approach_cargo_filter_value or approach_previous_cargo_filter_value %}
        {% if archive_date %}
          <a class="btn btn-secondary approach-filter-reset" title="Сбросить фильтры" href="{{ url_for('index', tab='approach', archive_date=archive_date) }}">×</a>
        {% else %}
          <a class="btn btn-secondary approach-filter-reset" title="Сбросить фильтры" href="{{ url_for('index', tab='approach') }}">×</a>
        {% endif %}
      {% endif %}
    </form>
    {% endif %}
    {% if allow_upload %}
    <form class="upload-form" method="post" action="{{ url_for('upload_file') }}" enctype="multipart/form-data">
      <input type="hidden" name="tab" value="{{ upload_tab }}">
      {% if current_tab == 'station_idle' %}<input type="hidden" name="idle_view" value="{{ station_idle_mode }}">{% endif %}
      <label class="file-label">
        <span>Выбрать Excel</span>
        <input type="file" name="excel_file" accept=".xlsx,.xls,.xlsm,.xltx,.xltm" required>
      </label>
      <button class="btn btn-primary" type="submit">Загрузить</button>
    </form>
    {% endif %}
    {% if allow_archive %}
    <form class="archive-form" method="get" action="{{ url_for('index') }}">
      <input type="hidden" name="tab" value="{{ current_tab }}">
      {% if current_tab == 'station_idle' %}<input type="hidden" name="idle_view" value="{{ station_idle_mode }}">{% endif %}
      <input class="archive-date" type="date" name="archive_date" value="{{ archive_date }}">
      <button class="btn btn-soft" type="submit">Открыть дату</button>
      {% if archive_date %}<a class="btn btn-secondary" href="{{ url_for('index', tab=current_tab) }}">Текущая</a>{% endif %}
    </form>
    {% endif %}
    <a class="btn btn-secondary" href="{{ url_for('refresh', tab=current_tab, archive_date=archive_date, idle_view=station_idle_mode if current_tab == 'station_idle' else None) }}">Обновить</a>
    {% if current_tab == 'approach' %}
      <a class="btn btn-soft" href="{{ url_for('export_summary', tab=current_tab, archive_date=archive_date, approach_cargo_filter=approach_cargo_filter_value, approach_previous_cargo_filter=approach_previous_cargo_filter_value) }}">Сводка Excel</a>
    {% else %}
      <a class="btn btn-soft" href="{{ url_for('export_summary', tab=current_tab, archive_date=archive_date, idle_view=station_idle_mode if current_tab == 'station_idle' else None) }}">Сводка Excel</a>
    {% endif %}
    {% if sample_available and upload_tab == 'approach' %}<a class="btn btn-soft" href="{{ url_for('load_sample', tab=current_tab) }}">Демо</a>{% endif %}
  </div>
</section>

{% if success_message %}<div class="success card">{{ success_message }}</div>{% endif %}
{% if error_message %}<div class="error card">{{ error_message }}</div>{% endif %}

<div class="header-grid {% if current_tab == 'departure' %}header-grid-departure{% else %}header-grid-approach{% endif %}">
  <section class="card search-card">
    <div class="search-caption">Поиск по номеру вагона</div>
    <form class="search-form" method="get" action="{{ url_for('search_wagon') }}">
      <input type="hidden" name="tab" value="{{ current_tab }}">
      {% if current_tab == 'station_idle' %}<input type="hidden" name="idle_view" value="{{ station_idle_mode }}">{% endif %}
      {% if archive_date %}<input type="hidden" name="archive_date" value="{{ archive_date }}">{% endif %}
      <input class="search-input" type="text" name="wagon" value="{{ search_value }}" placeholder="Введите точный номер вагона" autocomplete="off" required>
      <button class="btn btn-primary" type="submit">Найти</button>
    </form>
  </section>

  {% for item in metric_cards %}
    {% set metric_class = "card metric" %}
    {% if item.link %}{% set metric_class = metric_class + " metric-link" %}{% endif %}
    {% if item.danger %}{% set metric_class = metric_class + " metric-danger" %}{% endif %}
    {% if item.link %}
    <a class="{{ metric_class }}" href="{{ item.link }}">
      <div class="label">{{ item.label }}</div>
      <div class="value">{{ item.count }}</div>
      {% if item.sub %}<div class="sub">{{ item.sub }}</div>{% endif %}
    </a>
    {% else %}
    <section class="{{ metric_class }}">
      <div class="label">{{ item.label }}</div>
      <div class="value">{{ item.count }}</div>
      {% if item.sub %}<div class="sub">{{ item.sub }}</div>{% endif %}
    </section>
    {% endif %}
  {% endfor %}
</div>

<section class="card table-card">
  <div class="toolbar">
    <div>
      {% if summary_cargo_filter_label %}
      <form method="get" class="summary-filter-form">
        <input type="hidden" name="tab" value="{{ current_tab }}">
        {% if archive_date %}<input type="hidden" name="archive_date" value="{{ archive_date }}">{% endif %}
        <input type="hidden" name="idle_view" value="{{ station_idle_mode }}">
        <label class="summary-filter-box" for="summary-cargo-filter">
          <span class="summary-filter-label">{{ summary_cargo_filter_label }}</span>
          <select class="input summary-filter-select" id="summary-cargo-filter" name="cargo_name_filter" onchange="this.form.submit()">
            <option value="">Все грузы</option>
            {% for option in summary_cargo_filter_options %}
              <option value="{{ option }}" {% if option == summary_cargo_filter_value %}selected{% endif %}>{{ option }}</option>
            {% endfor %}
          </select>
        </label>
      </form>
      {% elif summary_title %}
      <div class="toolbar-title">{{ summary_title }}</div>
      {% endif %}
      {% if summary_sub %}<div class="toolbar-sub">{{ summary_sub }}</div>{% endif %}
      {% if network_hint %}<div class="toolbar-sub">Сеть: {{ network_hint }}</div>{% endif %}
    </div>
    <div class="toolbar-right">
      {% if show_expand_controls %}
      <button class="btn btn-ghost" type="button" id="expand-all-btn">Развернуть все</button>
      <button class="btn btn-ghost" type="button" id="collapse-all-btn">Свернуть все</button>
      {% endif %}
      {% if show_stop_rent_button %}<a class="btn btn-ghost" href="{{ url_for('stop_rent_access', tab=current_tab, archive_date=archive_date) }}">Стоп аренда</a>{% endif %}
    </div>
  </div>

  {% if raw_material_table %}
  {% if raw_material_rows %}
  <div class="table-wrap">
    <table class="summary-table raw-material-table">
      <thead>
        <tr>
          <th class="c-name raw-material-interval-col">{{ summary_first_column }}</th>
          {% for cargo_name in raw_material_headers %}
            <th class="num-col group-split">{{ cargo_name }}</th>
          {% endfor %}
        </tr>
      </thead>
      <tbody>
        {% for row in raw_material_rows %}
        <tr class="row-station">
          <td class="c-name raw-material-interval-col"><span class="summary-row-label">{{ row.label }}</span></td>
          {% for cargo_name in raw_material_headers %}
          <td class="num group-split">
            {% if row.counts.get(cargo_name, 0) > 0 %}<a class="cell-link" href="{{ row.links[cargo_name] }}">{{ row.counts.get(cargo_name, 0) }}</a>{% else %}<span class="cell-empty">—</span>{% endif %}
          </td>
          {% endfor %}
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% else %}
    <div class="empty">После фильтрации данные не найдены.</div>
  {% endif %}
  {% elif rows %}
  <div class="table-wrap">
    <table class="summary-table">
      <thead>
        <tr>
          <th class="c-name" rowspan="2">{{ summary_first_column }}</th>
          {% for col in category_order %}
            <th class="num-col group-split" colspan="{{ cargo_order|length }}">{{ col }}</th>
          {% endfor %}
        </tr>
        <tr>
          {% for col in category_order %}
            {% for cargo in cargo_order %}
              <th class="num-col {% if cargo == 'гр' %}group-split{% else %}cargo-split{% endif %}">{{ cargo }}</th>
            {% endfor %}
          {% endfor %}
        </tr>
      </thead>
      <tbody>
        {% for row in rows %}
        <tr class="row-{{ row.level }}{% if row.level == 'station' and row.cargo_name %} row-nested-bucket{% endif %}" {% if row.level == 'road' %}data-road-row="1" data-road="{{ row.road|e }}"{% endif %} {% if row.level in ['cargo', 'station'] %}data-station-row="1" data-road="{{ row.road|e }}"{% endif %}>
          <td class="c-name">
            <div class="name-wrap">
              {% if row.level == 'road' and show_expand_controls %}
                <button type="button" class="road-toggle" data-road-toggle="{{ row.road|e }}" aria-label="Свернуть или развернуть станции">▼</button>
              {% else %}
                <span class="road-placeholder"></span>
              {% endif %}
              {% if row.level == 'station' %}
                <span class="road-placeholder"></span>
              {% endif %}
              <div class="summary-row-main">
                {% if row.map_link %}
                  <a class="summary-row-link" href="{{ row.map_link }}" title="Показать на карте">{{ row.label }}</a>
                {% else %}
                  <span class="summary-row-label">{{ row.label }}</span>
                {% endif %}
              </div>
            </div>
          </td>

          {% for col in category_order %}
            {% for cargo in cargo_order %}
            <td class="num {% if cargo == 'гр' %}group-split{% else %}cargo-split{% endif %}">
              {% if row.counts[col][cargo] > 0 %}<a class="cell-link" href="{{ row.links[col][cargo] }}">{{ row.counts[col][cargo] }}</a>{% else %}<span class="cell-empty">—</span>{% endif %}
            </td>
            {% endfor %}
          {% endfor %}
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% else %}
    <div class="empty">После фильтрации данные не найдены.</div>
  {% endif %}
</section>

{% if not raw_material_table %}
<script>
(function(){
  const key = "asuCollapsedRoads_" + {{ current_tab|tojson }};
  function getCollapsedSet(){ try { const raw = localStorage.getItem(key); const arr = raw ? JSON.parse(raw) : []; return new Set(Array.isArray(arr) ? arr : []); } catch(e) { return new Set(); } }
  function saveCollapsedSet(set){ try { localStorage.setItem(key, JSON.stringify(Array.from(set))); } catch(e) {} }
  function applyRoadState(road, collapsed){
    document.querySelectorAll('tr[data-station-row="1"]').forEach(function(row){ if (row.getAttribute('data-road') === road) row.classList.toggle('is-collapsed', collapsed); });
    let toggle = null;
    document.querySelectorAll('[data-road-toggle]').forEach(function(btn){ if (btn.getAttribute('data-road-toggle') === road) toggle = btn; });
    if (toggle) { toggle.classList.toggle('is-collapsed', collapsed); toggle.textContent = collapsed ? '▶' : '▼'; }
  }
  const collapsedSet = getCollapsedSet();
  document.querySelectorAll('[data-road-toggle]').forEach(btn => {
    const road = btn.getAttribute('data-road-toggle');
    applyRoadState(road, collapsedSet.has(road));
    btn.addEventListener('click', function(){ const isCollapsed = collapsedSet.has(road); if (isCollapsed) collapsedSet.delete(road); else collapsedSet.add(road); saveCollapsedSet(collapsedSet); applyRoadState(road, !isCollapsed); });
  });
  const collapseAllBtn = document.getElementById('collapse-all-btn');
  const expandAllBtn = document.getElementById('expand-all-btn');
  if (collapseAllBtn) collapseAllBtn.addEventListener('click', function(){ document.querySelectorAll('[data-road-toggle]').forEach(btn => collapsedSet.add(btn.getAttribute('data-road-toggle'))); saveCollapsedSet(collapsedSet); document.querySelectorAll('[data-road-toggle]').forEach(btn => applyRoadState(btn.getAttribute('data-road-toggle'), true)); });
  if (expandAllBtn) expandAllBtn.addEventListener('click', function(){ collapsedSet.clear(); saveCollapsedSet(collapsedSet); document.querySelectorAll('[data-road-toggle]').forEach(btn => applyRoadState(btn.getAttribute('data-road-toggle'), false)); });
})();
</script>
{% endif %}
"""

DASHBOARD_BODY = """
<div class="dashboard-shell dashboard-fixed">
  <aside class="dashboard-side">
    <section class="side-card">
      <div class="quick-links">
        <details class="station-quick-select">
          <summary class="quick-link station-quick-summary">
            <div>
              <div class="quick-link-title">Выбрать станцию</div>
              <div class="station-quick-current">{% if selected_station %}{{ selected_station }}{% else %}Станция не выбрана{% endif %}</div>
            </div>
            <div class="quick-link-arrow">⌄</div>
          </summary>
          <form class="station-quick-form" method="post" action="{{ url_for('station_select') }}">
            <select name="station" class="station-quick-dropdown" onchange="this.form.submit()" required>
              <option value="">Выберите станцию</option>
              {% for station in station_options %}
                <option value="{{ station }}" {% if station == selected_station %}selected{% endif %}>{{ station }}</option>
              {% endfor %}
            </select>
            {% if selected_station %}
              <a class="station-quick-clear" href="{{ url_for('station_clear') }}">Сбросить выбор</a>
            {% endif %}
          </form>
        </details>
        {% for item in dashboard_links %}
        <a class="quick-link" href="{{ item.href }}">
          <div>
            <div class="quick-link-title">{{ item.title }}</div>
          </div>
          <div class="quick-link-arrow">›</div>
        </a>
        {% endfor %}
      </div>
    </section>
  </aside>

  <div class="dashboard-main">
    <section class="card dashboard-hero">
      <div class="dashboard-hero-head">
        <div>
          <h1 class="dashboard-hero-title">АСУ ПОДХОД — стартовая панель</h1>
          
        </div>
      </div>
      {% if selected_station %}
      <div class="dashboard-metrics">
        {% for item in dashboard_metrics %}
        <article class="card dash-metric">
          <div class="dash-metric-label">{{ item.label }}</div>
          <div class="dash-metric-value">{{ item.value }}</div>
          <div class="dash-metric-foot">
            <div class="dash-metric-trend {{ item.trend_class }}">{{ item.trend_label }}</div>
          </div>
        </article>
        {% endfor %}
      </div>
      {% else %}
      <div class="empty card">Выберите станцию для отображения данных.</div>
      {% endif %}
    </section>

    <div class="dashboard-grid-2">
      <section class="card map-card">
        <div class="map-head">
          <h2 class="section-title">Обзор предприятия</h2>
        </div>
        {% if selected_station %}
        <div class="hero-photo-stage">
          {% set station_name_lower = (selected_station or '')|lower %}
          {% if 'заяч' in station_name_lower %}
          <img src="{{ url_for('static', filename='dashboard_zayachya_gorka_overview.png') }}" alt="ЗАЯЧЬЯ ГОРКА" loading="eager">
          {% else %}
          <img src="{{ url_for('static', filename='dashboard_enterprise_overview.png') }}" alt="МЕТАФРАКС КЕМИКАЛС" loading="eager">
          {% endif %}
          <div class="hero-photo-overlay"></div>
        </div>
        {% else %}
        <div class="empty">Выберите станцию для отображения обзора.</div>
        {% endif %}
      </section>

      <section class="card events-card">
        <h2 class="section-title">Последние события</h2>
        <div class="events-list">
          {% for item in dashboard_events %}
          <div class="event-item">
            <div class="event-title">{{ item.title }}</div>
            <div class="event-time">{{ item.time }}</div>
            <div class="event-meta">{{ item.meta }}</div>
          </div>
          {% else %}
          <div class="empty">Нет данных для отображения.</div>
          {% endfor %}
        </div>
      </section>
    </div>
  </div>
</div>
<script>
(function(){
  const refreshSeconds = {{ dashboard_refresh_seconds|default(0) }};
  if (refreshSeconds > 0) {
    window.setTimeout(() => {
      const url = new URL(window.location.href);
      url.searchParams.set('_ts', String(Date.now()));
      window.location.replace(url.toString());
    }, refreshSeconds * 1000);
  }
})();
</script>
"""


STATION_SELECT_BODY = """
<div class="main-tabs">
  <a class="main-tab" href="{{ url_for('index', tab='dashboard') }}">Главный экран</a>
  <a class="main-tab is-active" href="{{ url_for('station_select') }}">Выбрать станцию</a>
  <a class="main-tab" href="{{ url_for('index', tab='approach') }}">Подход вагонов</a>
  <a class="main-tab" href="{{ url_for('index', tab='departure') }}">Отправление вагонов</a>
  <a class="main-tab" href="{{ url_for('index', tab='loading') }}">Погрузка</a>
  <a class="main-tab" href="{{ url_for('index', tab='station_idle') }}">Простои</a>
  <a class="main-tab" href="{{ url_for('index', tab='raw_material') }}">Сырье</a>
  <a class="main-tab" href="{{ url_for('technical_state_index') }}">Техническое состояние</a>
  <a class="main-tab" href="{{ url_for('index', tab='manual_filter') }}">Ручной фильтр</a>
  <a class="main-tab" href="{{ url_for('archive_search') }}">Архив</a>
  <a class="main-tab" href="{{ url_for('mailing_rules') }}">Авторассылка справок</a>
  <a class="main-tab main-tab-settings" href="{{ url_for('settings_page') }}">Настройки</a>
</div>

<section class="card topbar">
  <div class="topbar-left">
    <div class="title">{{ app_title }} — Выбрать станцию</div>
    <div class="meta">Текущая станция: {% if selected_station %}<b>{{ selected_station }}</b>{% else %}не выбрана{% endif %}</div>
  </div>
</section>

{% if success_message %}<div class="success card">{{ success_message }}</div>{% endif %}
{% if error_message %}<div class="error card">{{ error_message }}</div>{% endif %}

<section class="card settings-card">
  <h2 class="section-title">Рабочая станция</h2>
  <div class="section-sub">Выберите станцию, относительно которой будут строиться подход, отправление, погрузка, простои и связанные отчёты.</div>
  <form method="post" action="{{ url_for('station_select') }}" style="display:grid; gap:12px; max-width:720px; margin-top:14px;">
    <div class="field">
      <label>Станция</label>
      <input list="station-options" name="station" value="{{ selected_station }}" placeholder="Введите или выберите станцию" required>
      <datalist id="station-options">
        {% for station in station_options %}
          <option value="{{ station }}"></option>
        {% endfor %}
      </datalist>
    </div>
    <div style="display:flex; gap:8px; flex-wrap:wrap;">
      <button class="btn btn-primary" type="submit">Выбрать</button>
      {% if selected_station %}<a class="btn btn-secondary" href="{{ url_for('station_clear') }}">Сбросить выбор</a>{% endif %}
      <a class="btn btn-soft" href="{{ url_for('index', tab='dashboard') }}">На стартовую панель</a>
    </div>
  </form>
</section>
"""

SETTINGS_BODY = """
<div class="dashboard-shell" style="grid-template-columns: 1fr;">
  <section class="card dashboard-hero">
    <div class="dashboard-hero-head">
      <div>
        <h1 class="dashboard-hero-title">Настройки</h1>
        <div class="dashboard-hero-sub">Раздел персонализации АСУ ПОДХОД: внешний вид, стартовый экран, уведомления, каналы связи и Excel-выгрузки.</div>
      </div>
      <div class="dashboard-actions">
        <a class="btn btn-secondary" href="{{ url_for('index', tab='dashboard') }}">На главный экран</a>
      </div>
    </div>
  </section>

  {% if error_message %}<div class="error card">{{ error_message }}</div>{% endif %}
  {% if success_message %}<div class="success card">{{ success_message }}</div>{% endif %}

  <div class="settings-shell">
    <aside class="card side-card">
      <h2 class="section-title">Разделы настроек</h2>
      <div class="settings-nav">
        <a href="#appearance">Внешний вид</a>
        <a href="#dashboard-settings">Стартовый экран</a>
        <a href="#stations">Станции и источники справок</a>
        <a href="#channels">Каналы связи</a>
        <a href="#rules">Уведомления</a>
        <a href="#excel">Excel и выгрузки</a>
        <a href="#program">Поведение программы</a>
      </div>
    </aside>

    <div class="card settings-card">
      <section class="settings-block" id="appearance">
        <h2 class="settings-block-title">Внешний вид</h2>
        <form method="post" action="{{ url_for('settings_page') }}">
          <input type="hidden" name="action" value="save_appearance">
          <div class="settings-grid-form">
            <div class="field">
              <label>Тема</label>
              <select name="theme">
                <option value="light" {% if ui_preferences.theme == 'light' %}selected{% endif %}>Светлая</option>
                <option value="dark" {% if ui_preferences.theme == 'dark' %}selected{% endif %}>Тёмная</option>
                <option value="violet" {% if ui_preferences.theme == 'violet' %}selected{% endif %}>Фиолетовая</option>
                <option value="refinery" {% if ui_preferences.theme == 'refinery' %}selected{% endif %}>Химический завод</option>
              </select>
            </div>
            <div class="field">
              <label>Скругление</label>
              <select name="radius_style">
                <option value="compact" {% if ui_preferences.radius_style == 'compact' %}selected{% endif %}>Минимальное</option>
                <option value="medium" {% if ui_preferences.radius_style == 'medium' %}selected{% endif %}>Среднее</option>
                <option value="soft" {% if ui_preferences.radius_style == 'soft' %}selected{% endif %}>Мягкое</option>
              </select>
            </div>
            <div class="field">
              <label>Плотность интерфейса</label>
              <select name="density">
                <option value="compact" {% if ui_preferences.density == 'compact' %}selected{% endif %}>Компактно</option>
                <option value="standard" {% if ui_preferences.density == 'standard' %}selected{% endif %}>Стандартно</option>
              </select>
            </div>
            <div class="field">
              <label>Акцентный цвет</label>
              <input type="color" name="accent_color" value="{{ ui_preferences.accent_color }}">
            </div>
            <div class="field">
              <label>Цвет шрифта</label>
              <input type="color" name="font_color" value="{{ ui_preferences.font_color|default('#182433') }}">
            </div>
          </div>
          <div style="margin-top:10px;"><button class="btn btn-primary" type="submit">Сохранить внешний вид</button></div>
        </form>
      </section>

      <section class="settings-block" id="stations">
        <h2 class="settings-block-title">Станции и источники справок</h2>
        <div class="section-sub" style="margin-bottom:12px;">
          Базовая станция <b>{{ base_station_name }}</b> работает по старой схеме и здесь не редактируется.
          Этот блок предназначен только для добавляемых станций: например, Заячья Горка и последующие станции.
        </div>

        <form method="post" action="{{ url_for('settings_page') }}#stations">
          <input type="hidden" name="action" value="save_station_source">
          <div class="settings-grid-form">
            <div class="field">
              <label>Наименование станции</label>
              <input type="text" name="station_name" placeholder="Например: Заячья Горка" required>
            </div>
            <div class="field">
              <label>Почтовая учётная запись</label>
              <input type="text" value="{{ imap_username or 'используется текущая почта программы' }}" readonly>
            </div>
            <div class="field field-check">
              <input type="checkbox" name="station_enabled" value="1" checked>
              <label style="text-transform:none; letter-spacing:0;">Показывать станцию в списке выбора</label>
            </div>

            <div class="field" style="grid-column:1 / -1;"><b>Подход вагонов</b></div>
            <div class="field">
              <label>Папка почты</label>
              <input type="text" name="approach_mailbox" placeholder="Например: АСУ ПОДХОД/Заячья Горка/Подход" required>
            </div>
            <div class="field">
              <label>Часть темы письма</label>
              <input type="text" name="approach_subject_filter" placeholder="Можно оставить пустым">
            </div>
            <div class="field">
              <label>Точная тема письма</label>
              <input type="text" name="approach_subject_equals" placeholder="Если нужна точная тема">
            </div>
            <div class="field">
              <label>Маска/часть имени файла</label>
              <input type="text" name="approach_attachment_name_contains" placeholder="Например: .xlsx">
            </div>
            <div class="field">
              <label>Точное имя файла</label>
              <input type="text" name="approach_attachment_name_equals" placeholder="Если нужно точное имя">
            </div>

            <div class="field" style="grid-column:1 / -1;"><b>Отправление вагонов</b></div>
            <div class="field">
              <label>Папка почты</label>
              <input type="text" name="departure_mailbox" placeholder="Например: АСУ ПОДХОД/Заячья Горка/Отправление" required>
            </div>
            <div class="field">
              <label>Часть темы письма</label>
              <input type="text" name="departure_subject_filter" placeholder="Можно оставить пустым">
            </div>
            <div class="field">
              <label>Точная тема письма</label>
              <input type="text" name="departure_subject_equals" placeholder="Если нужна точная тема">
            </div>
            <div class="field">
              <label>Маска/часть имени файла</label>
              <input type="text" name="departure_attachment_name_contains" placeholder="Например: .xlsx">
            </div>
            <div class="field">
              <label>Точное имя файла</label>
              <input type="text" name="departure_attachment_name_equals" placeholder="Если нужно точное имя">
            </div>

            <div class="field" style="grid-column:1 / -1;"><b>Быстрые направления для добавленной станции</b></div>
            <div class="field" style="grid-column:1 / -1;">
              <label>Подход вагонов: стандартные кнопки</label>
              <div class="inline-checks" style="display:flex; gap:10px; flex-wrap:wrap;">
                {% for direction in approach_default_direction_cards %}
                  <label class="field-check" style="display:flex; align-items:center; gap:6px; margin:0;">
                    <input type="checkbox" name="approach_direction_enabled" value="{{ direction }}" checked>
                    <span>{{ direction }}</span>
                  </label>
                {% endfor %}
              </div>
              <div class="section-sub" style="margin-top:4px;">Снимите галочку, чтобы скрыть стандартную кнопку в разделе «Подход вагонов» для этой добавленной станции.</div>
            </div>
            <div class="field" style="grid-column:1 / -1;">
              <label>Подход вагонов: новые направления</label>
              <textarea name="approach_custom_directions" rows="2" placeholder="Например: Новороссийск&#10;Туапсе"></textarea>
              <div class="section-sub" style="margin-top:4px;">Каждое направление вводите с новой строки или через запятую. Новые кнопки будут работать по той же логике, что текущие направления.</div>
            </div>

            <div class="field" style="grid-column:1 / -1;">
              <label>Отправление вагонов: стандартные кнопки</label>
              <div class="inline-checks" style="display:flex; gap:10px; flex-wrap:wrap;">
                {% for direction in departure_default_direction_cards %}
                  <label class="field-check" style="display:flex; align-items:center; gap:6px; margin:0;">
                    <input type="checkbox" name="departure_direction_enabled" value="{{ direction }}" checked>
                    <span>{{ direction }}</span>
                  </label>
                {% endfor %}
              </div>
              <div class="section-sub" style="margin-top:4px;">Снимите галочку, чтобы скрыть стандартную кнопку в разделе «Отправление вагонов» для этой добавленной станции.</div>
            </div>
            <div class="field" style="grid-column:1 / -1;">
              <label>Отправление вагонов: новые направления</label>
              <textarea name="departure_custom_directions" rows="2" placeholder="Например: Новороссийск&#10;Туапсе"></textarea>
              <div class="section-sub" style="margin-top:4px;">Добавленные направления будут показывать вагоны, прогресс проследования и процентное соотношение по той же логике, что текущие кнопки.</div>
            </div>
          </div>
          <div style="margin-top:10px;"><button class="btn btn-primary" type="submit">Сохранить станцию</button></div>
        </form>

        {% if station_sources %}
        <div style="margin-top:18px;">
          <h3 class="section-title">Добавленные станции</h3>
          <div class="table-wrap">
            <table class="detail-table">
              <thead>
                <tr>
                  <th>Станция</th>
                  <th>Подход: папка</th>
                  <th>Подход: файл/тема</th>
                  <th>Отправление: папка</th>
                  <th>Отправление: файл/тема</th>
                  <th>Подход: кнопки</th>
                  <th>Отправление: кнопки</th>
                  <th style="width:120px;">Действие</th>
                </tr>
              </thead>
              <tbody>
                {% for item in station_sources %}
                <tr>
                  <td><b>{{ item.name }}</b>{% if not item.enabled %}<br><span class="muted">скрыта</span>{% endif %}</td>
                  <td>{{ item.approach.mailbox or '—' }}</td>
                  <td>{{ item.approach.attachment_name_contains or item.approach.subject_filter or item.approach.subject_equals or '—' }}</td>
                  <td>{{ item.departure.mailbox or '—' }}</td>
                  <td>{{ item.departure.attachment_name_contains or item.departure.subject_filter or item.departure.subject_equals or '—' }}</td>
                  <td>
                    {% set approach_dirs = item.directions.approach|selectattr('enabled')|list %}
                    {% if approach_dirs %}{% for direction in approach_dirs %}{{ direction.name }}{% if not loop.last %}, {% endif %}{% endfor %}{% else %}—{% endif %}
                  </td>
                  <td>
                    {% set departure_dirs = item.directions.departure|selectattr('enabled')|list %}
                    {% if departure_dirs %}{% for direction in departure_dirs %}{{ direction.name }}{% if not loop.last %}, {% endif %}{% endfor %}{% else %}—{% endif %}
                  </td>
                  <td>
                    <form method="post" action="{{ url_for('settings_page') }}#stations" onsubmit="return confirm('Удалить добавленную станцию?');">
                      <input type="hidden" name="action" value="delete_station_source">
                      <input type="hidden" name="station_name" value="{{ item.name }}">
                      <button class="btn btn-soft" type="submit">Удалить</button>
                    </form>
                  </td>
                </tr>
                <tr>
                  <td colspan="8">
                    <details>
                      <summary style="cursor:pointer; font-weight:700;">Настроить быстрые направления для {{ item.name }}</summary>
                      <form method="post" action="{{ url_for('settings_page') }}#stations" style="margin-top:10px; display:grid; gap:10px;">
                        <input type="hidden" name="action" value="save_station_directions">
                        <input type="hidden" name="station_name" value="{{ item.name }}">

                        {% set approach_enabled_names = item.directions.approach|selectattr('enabled')|map(attribute='name')|list %}
                        {% set departure_enabled_names = item.directions.departure|selectattr('enabled')|map(attribute='name')|list %}
                        {% set approach_custom_names = [] %}
                        {% for direction in item.directions.approach %}
                          {% if direction.enabled and direction.name not in approach_default_direction_cards %}
                            {% set _ = approach_custom_names.append(direction.name) %}
                          {% endif %}
                        {% endfor %}
                        {% set departure_custom_names = [] %}
                        {% for direction in item.directions.departure %}
                          {% if direction.enabled and direction.name not in departure_default_direction_cards %}
                            {% set _ = departure_custom_names.append(direction.name) %}
                          {% endif %}
                        {% endfor %}

                        <div class="settings-grid-form">
                          <div class="field" style="grid-column:1 / -1;">
                            <label>Подход вагонов: стандартные кнопки</label>
                            <div class="inline-checks" style="display:flex; gap:10px; flex-wrap:wrap;">
                              {% for direction in approach_default_direction_cards %}
                                <label class="field-check" style="display:flex; align-items:center; gap:6px; margin:0;">
                                  <input type="checkbox" name="approach_direction_enabled" value="{{ direction }}" {% if direction in approach_enabled_names %}checked{% endif %}>
                                  <span>{{ direction }}</span>
                                </label>
                              {% endfor %}
                            </div>
                          </div>
                          <div class="field" style="grid-column:1 / -1;">
                            <label>Подход вагонов: новые направления</label>
                            <textarea name="approach_custom_directions" rows="2">{{ approach_custom_names|join('\n') }}</textarea>
                          </div>
                          <div class="field" style="grid-column:1 / -1;">
                            <label>Отправление вагонов: стандартные кнопки</label>
                            <div class="inline-checks" style="display:flex; gap:10px; flex-wrap:wrap;">
                              {% for direction in departure_default_direction_cards %}
                                <label class="field-check" style="display:flex; align-items:center; gap:6px; margin:0;">
                                  <input type="checkbox" name="departure_direction_enabled" value="{{ direction }}" {% if direction in departure_enabled_names %}checked{% endif %}>
                                  <span>{{ direction }}</span>
                                </label>
                              {% endfor %}
                            </div>
                          </div>
                          <div class="field" style="grid-column:1 / -1;">
                            <label>Отправление вагонов: новые направления</label>
                            <textarea name="departure_custom_directions" rows="2">{{ departure_custom_names|join('\n') }}</textarea>
                          </div>
                        </div>
                        <div><button class="btn btn-primary" type="submit">Сохранить направления</button></div>
                      </form>
                    </details>
                  </td>
                </tr>
                {% endfor %}
              </tbody>
            </table>
          </div>
          <div class="section-sub" style="margin-top:8px;">
            Для раздела «Техническое состояние» программа использует сразу две справки выбранной станции: «Подход вагонов» и «Отправление вагонов».
          </div>
        </div>
        {% else %}
          <div class="empty" style="margin-top:14px;">Добавленных станций пока нет. Углеуральская работает по существующей схеме.</div>
        {% endif %}
      </section>

      <section class="settings-block" id="dashboard-settings">
        <h2 class="settings-block-title">Стартовый экран</h2>
        <form method="post" action="{{ url_for('settings_page') }}">
          <input type="hidden" name="action" value="save_dashboard">
          <div class="settings-grid-form">
            <div class="field">
              <label>Вид карты по умолчанию</label>
              <select name="default_map_view">
                <option value="loaded" {% if ui_preferences.default_map_view == 'loaded' %}selected{% endif %}>Гружёные</option>
                <option value="empty" {% if ui_preferences.default_map_view == 'empty' %}selected{% endif %}>Порожние</option>
                <option value="all" {% if ui_preferences.default_map_view == 'all' %}selected{% endif %}>Все</option>
              </select>
            </div>
            <div class="field">
              <label>Количество событий</label>
              <input type="number" name="dashboard_events_limit" min="3" max="20" value="{{ ui_preferences.dashboard_events_limit }}">
            </div>
            <div class="field field-check">
              <input type="checkbox" name="dashboard_show_map" value="1" {% if ui_preferences.dashboard_show_map %}checked{% endif %}>
              <label style="text-transform:none; letter-spacing:0;">Показывать карту на стартовом экране</label>
            </div>
          </div>
          <div style="margin-top:10px;"><button class="btn btn-primary" type="submit">Сохранить стартовый экран</button></div>
        </form>
      </section>

      <section class="settings-block" id="channels">
        <h2 class="settings-block-title">Каналы связи</h2>
        <form method="post" action="{{ url_for('settings_page') }}">
          <input type="hidden" name="action" value="save_channel">
          <div class="settings-grid-form">
            <div class="field">
              <label>Основной канал</label>
              <select name="channel_type">
                <option value="app" {% if notification_channel.channel_type == 'app' %}selected{% endif %}>Только внутри программы</option>
                <option value="telegram" {% if notification_channel.channel_type == 'telegram' %}selected{% endif %}>Telegram</option>
                <option value="whatsapp" {% if notification_channel.channel_type == 'whatsapp' %}selected{% endif %}>WhatsApp</option>
                <option value="max" {% if notification_channel.channel_type == 'max' %}selected{% endif %}>MAX</option>
              </select>
            </div>
            <div class="field">
              <label>Номер телефона</label>
              <input type="text" name="phone" value="{{ notification_channel.phone }}" placeholder="Например: +79990001122">
            </div>
            <div class="field">
              <label>Telegram</label>
              <input type="text" name="telegram_target" value="{{ notification_channel.telegram_target }}" placeholder="@dispatcher или chat_id">
            </div>
            <div class="field">
              <label>WhatsApp</label>
              <input type="text" name="whatsapp_target" value="{{ notification_channel.whatsapp_target }}" placeholder="Номер или ID">
            </div>
            <div class="field">
              <label>MAX</label>
              <input type="text" name="max_target" value="{{ notification_channel.max_target }}" placeholder="Номер или аккаунт">
            </div>
            <div class="field" style="grid-column: 1 / -1;">
              <label>URL webhook / токен</label>
              <input type="text" name="channel_url" value="{{ notification_channel.channel_url }}" placeholder="При фактическом подключении внешнего канала">
            </div>
            <div class="field" style="grid-column: 1 / -1;">
              <label>Комментарий</label>
              <textarea name="channel_comment">{{ notification_channel.channel_comment }}</textarea>
            </div>
          </div>
          <div style="margin-top:10px;"><button class="btn btn-primary" type="submit">Сохранить каналы связи</button></div>
        </form>
      </section>

      <section class="settings-block" id="rules">
        <h2 class="settings-block-title">Правила уведомлений</h2>
        <form method="post" action="{{ url_for('settings_page') }}">
          <input type="hidden" name="action" value="add_rule">
          <div class="settings-grid-form">
            <div class="field">
              <label>Название правила</label>
              <input type="text" name="rule_name" placeholder="Например: Ейск — прибытие поезда">
            </div>
            <div class="field">
              <label>Событие</label>
              <select name="event_type">
                <option value="departure">Отправление</option>
                <option value="arrival">Прибытие</option>
                <option value="operation_changed">Смена операции</option>
                <option value="idle_started">Начало простоя</option>
              </select>
            </div>
            <div class="field">
              <label>Объект</label>
              <select name="entity_type">
                <option value="wagon">Вагон</option>
                <option value="train">Поезд</option>
              </select>
            </div>
            <div class="field">
              <label>Канал доставки</label>
              <select name="delivery_channel">
                <option value="app">Внутри программы</option>
                <option value="telegram">Telegram</option>
                <option value="whatsapp">WhatsApp</option>
                <option value="max">MAX</option>
              </select>
            </div>
            <div class="field">
              <label>Индекс поезда</label>
              <input type="text" name="train_index" placeholder="Например: ПОВОРИНО+740+ПЕНЗА 3">
            </div>
            <div class="field">
              <label>Номер вагона</label>
              <input type="text" name="wagon_number" placeholder="Например: 56789012">
            </div>
            <div class="field">
              <label>Станция</label>
              <input type="text" name="station_name" placeholder="Например: Углеуральская">
            </div>
            <div class="field">
              <label>Состояние вагона</label>
              <select name="cargo_state">
                <option value="all">Все</option>
                <option value="гр">Гружёные</option>
                <option value="пор">Порожние</option>
              </select>
            </div>
            <div class="field" style="grid-column: 1 / -1;">
              <label>Примечание</label>
              <textarea name="rule_note" placeholder="Например: уведомить, если поезд прибыл на Углеуральскую"></textarea>
            </div>
          </div>
          <div style="margin-top:10px;"><button class="btn btn-primary" type="submit">Добавить правило</button></div>
        </form>

        <table class="settings-table" style="margin-top:12px;">
          <thead><tr><th>Правило</th><th>Событие</th><th>Канал</th><th>Условия</th><th></th></tr></thead>
          <tbody>
            {% for item in notification_rules %}
            <tr>
              <td><strong>{{ item.name }}</strong><br><span class="section-sub">{{ item.note or 'Без примечания' }}</span></td>
              <td><span class="pill">{{ item.event_label }}</span></td>
              <td>{{ item.channel_label }}</td>
              <td>{{ item.condition_label }}</td>
              <td>
                <form method="post" action="{{ url_for('settings_page') }}" onsubmit="return confirm('Удалить правило?');">
                  <input type="hidden" name="action" value="delete_rule">
                  <input type="hidden" name="rule_id" value="{{ item.id }}">
                  <button class="btn btn-secondary" type="submit">Удалить</button>
                </form>
              </td>
            </tr>
            {% else %}
            <tr><td colspan="5" class="empty">Пока правил нет.</td></tr>
            {% endfor %}
          </tbody>
        </table>
      </section>

      <section class="settings-block" id="excel">
        <h2 class="settings-block-title">Excel и выгрузки</h2>
        <form method="post" action="{{ url_for('settings_page') }}">
          <input type="hidden" name="action" value="save_export">
          <div class="settings-grid-form">
            <div class="field field-check"><input type="checkbox" name="excel_as_table" value="1" {% if export_preferences.excel_as_table %}checked{% endif %}><label style="text-transform:none; letter-spacing:0;">Выгружать как таблицу</label></div>
            <div class="field field-check"><input type="checkbox" name="excel_with_filters" value="1" {% if export_preferences.excel_with_filters %}checked{% endif %}><label style="text-transform:none; letter-spacing:0;">Добавлять фильтры</label></div>
            <div class="field field-check"><input type="checkbox" name="excel_with_borders" value="1" {% if export_preferences.excel_with_borders %}checked{% endif %}><label style="text-transform:none; letter-spacing:0;">Добавлять границы</label></div>
            <div class="field field-check"><input type="checkbox" name="excel_freeze_header" value="1" {% if export_preferences.excel_freeze_header %}checked{% endif %}><label style="text-transform:none; letter-spacing:0;">Закреплять первую строку</label></div>
            <div class="field">
              <label>Цвет заголовка</label>
              <input type="color" name="excel_header_color" value="{{ export_preferences.excel_header_color }}">
            </div>
            <div class="field">
              <label>Цвет текста заголовка</label>
              <input type="color" name="excel_header_font_color" value="{{ export_preferences.excel_header_font_color }}">
            </div>
          </div>
          <div style="margin-top:10px;"><button class="btn btn-primary" type="submit">Сохранить выгрузку Excel</button></div>
        </form>
      </section>

      <section class="settings-block" id="program">
        <h2 class="settings-block-title">Поведение программы</h2>
        <form method="post" action="{{ url_for('settings_page') }}">
          <input type="hidden" name="action" value="save_program">
          <div class="settings-grid-form">
            <div class="field">
              <label>Открывать при запуске</label>
              <select name="startup_tab">
                <option value="dashboard" {% if ui_preferences.startup_tab == 'dashboard' %}selected{% endif %}>Главный экран</option>
                <option value="approach" {% if ui_preferences.startup_tab == 'approach' %}selected{% endif %}>Подход вагонов</option>
                <option value="departure" {% if ui_preferences.startup_tab == 'departure' %}selected{% endif %}>Отправление вагонов</option>
              </select>
            </div>
            <div class="field">
              <label>Автообновление главной панели, сек.</label>
              <input type="number" name="dashboard_refresh_seconds" min="0" max="3600" value="{{ ui_preferences.dashboard_refresh_seconds }}">
            </div>
          </div>
          <div style="margin-top:10px;"><button class="btn btn-primary" type="submit">Сохранить поведение программы</button></div>
        </form>
      </section>
    </div>
  </div>
</div>
"""

DETAIL_BODY = """
<div class="main-tabs">
  <a class="main-tab {% if current_tab == 'dashboard' %}is-active{% endif %}" href="{{ url_for('index', tab='dashboard') }}">Главный экран</a>
  <a class="main-tab {% if current_tab == 'approach' %}is-active{% endif %}" href="{{ url_for('index', tab='approach', archive_date=archive_date) }}">Подход вагонов</a>
  <a class="main-tab {% if current_tab == 'departure' %}is-active{% endif %}" href="{{ url_for('index', tab='departure', archive_date=archive_date) }}">Отправление вагонов</a>
  <a class="main-tab {% if current_tab == 'loading' %}is-active{% endif %}" href="{{ url_for('index', tab='loading', archive_date=archive_date) }}">Погрузка</a>
  <a class="main-tab {% if current_tab == 'station_idle' %}is-active{% endif %}" href="{{ url_for('index', tab='station_idle', archive_date=archive_date) }}">Простои</a>
  <a class="main-tab {% if current_tab == 'raw_material' %}is-active{% endif %}" href="{{ url_for('index', tab='raw_material', archive_date=archive_date) }}">Сырье</a>
  <a class="main-tab {% if current_tab == 'technical_state' %}is-active{% endif %}" href="{{ url_for('technical_state_index') }}">Техническое состояние</a>
  <a class="main-tab {% if current_tab == 'manual_filter' %}is-active{% endif %}" href="{{ url_for('index', tab='manual_filter', archive_date=archive_date) }}">Ручной фильтр</a>
  <a class="main-tab main-tab-settings {% if current_tab == 'settings' %}is-active{% endif %}" href="{{ url_for('settings_page') }}">Настройки</a>
</div>

{% if current_tab == 'station_idle' %}
<div class="sub-tabs">
  <a class="sub-tab {% if station_idle_mode == 'ugleuralskaya' %}is-active{% endif %}" href="{{ url_for('index', tab='station_idle', idle_view='ugleuralskaya', archive_date=archive_date) }}">Простой на станции {{ selected_station or destination_keyword or "Углеуральская" }}</a>
  <a class="sub-tab {% if station_idle_mode == 'destination' %}is-active{% endif %}" href="{{ url_for('index', tab='station_idle', idle_view='destination', archive_date=archive_date) }}">Простой на станции назначения</a>
  <a class="sub-tab" href="{{ url_for('claims_ugleuralskaya_index') }}">Претензии на {{ selected_station or destination_keyword or "Углеуральской" }}</a>
</div>
{% endif %}

{% if current_tab == 'loading' %}
<div class="sub-tabs">
  <a class="sub-tab {% if loading_mode == 'today' %}is-active{% endif %}" href="{{ url_for('index', tab='loading', loading_view='today', archive_date=archive_date) }}">Погрузка сегодня</a>
  <a class="sub-tab {% if loading_mode == 'yesterday' %}is-active{% endif %}" href="{{ url_for('index', tab='loading', loading_view='yesterday', archive_date=archive_date) }}">Погрузка вчера</a>
  <a class="sub-tab {% if loading_mode == 'pending' %}is-active{% endif %}" href="{{ url_for('index', tab='loading', loading_view='pending', archive_date=archive_date) }}">Погружены, но не отправлены более суток</a>
</div>
{% endif %}

<div class="breadcrumb">
  <a href="{{ url_for('index', tab=current_tab, archive_date=archive_date, idle_view=station_idle_mode if current_tab == 'station_idle' else None, loading_view=loading_mode if current_tab == 'loading' else None) }}">Назад к сводке</a>
  <span>•</span>
  <span>{{ current_tab_label }}</span>
  {% if archive_date %}<span>• Архив: {{ archive_date }}</span>{% endif %}
</div>

{% if error_message %}<div class="error card">{{ error_message }}</div>{% endif %}

{% if train_rows %}
<section class="card train-board">
  <div class="toolbar" style="margin:-12px -12px 12px -12px;">
    <div>
      <div class="toolbar-title">Карточки поездов</div>
      <div class="toolbar-sub">Презентационное представление</div>
    </div>
  </div>
  <div class="train-board-grid">
    {% for item in train_rows %}
    <article class="train-item">
      <div class="train-item-head">
        <div>
          <div class="train-item-title">{{ item.destination or "Без назначения" }}</div>
          <div class="train-item-sub">{{ item.station }}{% if item.road %} • {{ item.road }}{% endif %}</div>
        </div>
        {% if item.detail_link %}
        <a class="train-item-badge train-item-badge-link" href="{{ item.detail_link }}">{{ item.wagon_count }}</a>
        {% else %}
        <div class="train-item-badge">{{ item.wagon_count }}</div>
        {% endif %}
      </div>
      <div class="train-progress">
        <div class="train-progress-meta">
          <span>Пройдено: {{ item.distance_done or "0" }} км</span>
          <span>{{ item.progress_label }}</span>
          <span>Осталось: {{ item.distance_left or "0" }} км</span>
        </div>
        <div class="train-progress-bar"><div class="train-progress-fill {{ item.progress_class }}" style="width: {{ item.progress_percent }}%;"></div></div>
      </div>
      <div class="train-fields">
        <div class="train-field"><div class="train-field-label">Индекс поезда</div><div class="train-field-value mono">{{ item.train_index }}</div></div>
        <div class="train-field"><div class="train-field-label">Операция</div><div class="train-field-value">{{ item.operation }}</div></div>
        <div class="train-field"><div class="train-field-label">Дата/время операции</div><div class="train-field-value">{{ item.operation_time }}</div></div>
        <div class="train-field"><div class="train-field-label">Простой</div><div class="train-field-value">{{ item.idle_time }}</div></div>
        {% if item.show_weight %}<div class="train-field"><div class="train-field-label">Вес, кг</div><div class="train-field-value">{{ item.weight_total }}</div></div>{% endif %}
        <div class="train-field"><div class="train-field-label">Начало рейса</div><div class="train-field-value">{{ item.trip_start }}</div></div>
      </div>
    </article>
    {% endfor %}
  </div>
</section>
{% endif %}

<section class="card detail-head">
  <div>
    <h1 class="detail-title">Детализация</h1>
    <div class="toolbar-sub">{{ filter_caption }}</div>
  </div>
  <div class="chips">
    <span class="chip">Всего: {{ total_count }}</span>
    {% if destination_label %}<span class="chip">Назначение: {{ destination_label }}</span>{% endif %}
    {% if origin_label %}<span class="chip">Отправление: {{ origin_label }}</span>{% endif %}
    {% if station %}<span class="chip">{{ station }}</span>{% endif %}
    {% if kind %}<span class="chip">{{ kind }}</span>{% endif %}
    {% if cargo_label %}<span class="chip">{{ cargo_label }}</span>{% endif %}
    {% if raw_material_cargo_label %}<span class="chip">Груз: {{ raw_material_cargo_label }}</span>{% endif %}
    {% if raw_material_idle_label %}<span class="chip">{{ raw_material_idle_label }}</span>{% endif %}
    {% if idle_bucket_label %}<span class="chip">{{ idle_bucket_label }}</span>{% endif %}
    {% if exact_wagon %}<span class="chip">Вагон: {{ exact_wagon }}</span>{% endif %}
    {% if show_detail_table %}
      <form method="post" action="{{ export_link }}" id="detail-export-form" style="display:none;">
        <input type="hidden" name="filtered_rows" id="detail-filtered-rows" value="">
      </form>
      <button class="btn btn-soft" type="submit" form="detail-export-form">Excel</button>
      <a class="btn btn-soft" href="{{ raw_export_link }}">Исходные</a>
    {% endif %}
  </div>
</section>

{% if wagon_search_summary %}
<section class="card" style="margin-bottom:12px;">
  <div class="toolbar">
    <div>
      <div class="toolbar-title">Результат поиска по вагонам</div>
      <div class="toolbar-sub">Запрошено {{ wagon_search_summary.requested_count }} вагонов, найдено {{ wagon_search_summary.found_count }} вагонов.</div>
      {% if wagon_search_summary.missing_wagons %}
      <div class="toolbar-sub" style="margin-top:8px;"><strong>Нет информации:</strong> {{ wagon_search_summary.missing_wagons | join(', ') }}</div>
      {% endif %}
    </div>
  </div>
</section>
{% endif %}

{% if not show_detail_table %}
  {% if not train_rows %}<section class="card"><div class="empty">Подходящих поездов для презентационной части не найдено.</div></section>{% endif %}
{% else %}
{% if destination_cargo_summary %}
<section class="card table-card" style="margin-bottom:12px;">
  <div class="toolbar">
    <div>
      <div class="toolbar-title">Грузы по станции назначения</div>
      <div class="toolbar-sub">{{ destination_cargo_summary_title }} • Всего вагонов: {{ destination_cargo_total }} • Грузов: {{ destination_cargo_unique_count }}</div>
    </div>
    <div class="toolbar-right">
      {% if destination_cargo_reset_link %}<a class="btn btn-ghost" href="{{ destination_cargo_reset_link }}">Все грузы</a>{% endif %}
    </div>
  </div>
  <div class="table-wrap">
    <table class="detail-table">
      <thead>
        <tr>
          <th>Груз</th>
          <th style="width:140px;">Вагонов</th>
          <th style="width:220px;">Действие</th>
        </tr>
      </thead>
      <tbody>
        {% for item in destination_cargo_summary %}
        <tr>
          <td>{{ item.cargo_name }}</td>
          <td>{{ item.count }}</td>
          <td>
            {% if item.link %}
            <a class="btn btn-soft" href="{{ item.link }}">Показать вагоны</a>
            {% else %}
            <span class="badge">Выбранный груз</span>
            {% endif %}
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</section>
{% endif %}
<section class="card table-card">
  <div class="toolbar">
    <div><div class="toolbar-title">Детализация</div></div>
    <div class="toolbar-right"><span class="badge" id="visible-count-badge">Показано: {{ total_count }}</span><button class="btn btn-ghost" type="button" id="clear-detail-filters">Сбросить фильтры</button></div>
  </div>
  <div class="table-wrap">
    <table class="detail-table" id="detail-table">
      <thead>
        <tr>
          <th class="detail-col-wagon" data-col-index="0"><div class="th-wrap"><span>№ ваг.</span><button type="button" class="col-filter-btn" data-col-index="0">▾</button></div></th>
          <th class="detail-col-kind" data-col-index="1"><div class="th-wrap"><span>Род ваг.</span><button type="button" class="col-filter-btn" data-col-index="1">▾</button></div></th>
          <th class="detail-col-date" data-col-index="2"><div class="th-wrap"><span>Нач. рейса</span><button type="button" class="col-filter-btn" data-col-index="2">▾</button></div></th>
          <th class="detail-col-date" data-col-index="3"><div class="th-wrap"><span>Дата и время окончания рейса</span><button type="button" class="col-filter-btn" data-col-index="3">▾</button></div></th>
          <th class="detail-col-road" data-col-index="4"><div class="th-wrap"><span>Дор. отпр.</span><button type="button" class="col-filter-btn" data-col-index="4">▾</button></div></th>
          <th class="detail-col-station" data-col-index="5"><div class="th-wrap"><span>Ст. отпр.</span><button type="button" class="col-filter-btn" data-col-index="5">▾</button></div></th>
          <th class="detail-col-road" data-col-index="6"><div class="th-wrap"><span>Дор. назн.</span><button type="button" class="col-filter-btn" data-col-index="6">▾</button></div></th>
          <th class="detail-col-dest" data-col-index="7"><div class="th-wrap"><span>Ст. назн.</span><button type="button" class="col-filter-btn" data-col-index="7">▾</button></div></th>
          <th class="detail-col-owner" data-col-index="8"><div class="th-wrap"><span>Грузоотпр.</span><button type="button" class="col-filter-btn" data-col-index="8">▾</button></div></th>
          <th class="detail-col-cargo" data-col-index="9"><div class="th-wrap"><span>Груз</span><button type="button" class="col-filter-btn" data-col-index="9">▾</button></div></th>
          <th class="detail-col-cargo" data-col-index="10"><div class="th-wrap"><span>Ранее выгруженный груз</span><button type="button" class="col-filter-btn" data-col-index="10">▾</button></div></th>
          <th class="detail-col-weight" data-col-index="11"><div class="th-wrap"><span>Вес, кг</span><button type="button" class="col-filter-btn" data-col-index="11">▾</button></div></th>
          <th class="detail-col-station" data-col-index="12"><div class="th-wrap"><span>Ст. опер.</span><button type="button" class="col-filter-btn" data-col-index="12">▾</button></div></th>
          <th class="detail-col-road" data-col-index="13"><div class="th-wrap"><span>Дор. опер.</span><button type="button" class="col-filter-btn" data-col-index="13">▾</button></div></th>
          <th class="detail-col-op" data-col-index="14"><div class="th-wrap"><span>Опер.</span><button type="button" class="col-filter-btn" data-col-index="14">▾</button></div></th>
          <th class="detail-col-date" data-col-index="15"><div class="th-wrap"><span>Дата/время опер.</span><button type="button" class="col-filter-btn" data-col-index="15">▾</button></div></th>
          <th class="detail-col-train" data-col-index="16"><div class="th-wrap"><span>Индекс поезда</span><button type="button" class="col-filter-btn" data-col-index="16">▾</button></div></th>
          <th class="detail-col-cargo" data-col-index="17"><div class="th-wrap"><span>Контейнеры</span><button type="button" class="col-filter-btn" data-col-index="17">▾</button></div></th>
          <th class="detail-col-date" data-col-index="18"><div class="th-wrap"><span>Норм. срок</span><button type="button" class="col-filter-btn" data-col-index="18">▾</button></div></th>
          <th class="detail-col-dist" data-col-index="19"><div class="th-wrap"><span>Пройд., км</span><button type="button" class="col-filter-btn" data-col-index="19">▾</button></div></th>
          <th class="detail-col-dist" data-col-index="20"><div class="th-wrap"><span>Ост., км</span><button type="button" class="col-filter-btn" data-col-index="20">▾</button></div></th>
          <th class="detail-col-date" data-col-index="21"><div class="th-wrap"><span>Простой, сут.</span><button type="button" class="col-filter-btn" data-col-index="21">▾</button></div></th>
          <th class="detail-col-date" data-col-index="22"><div class="th-wrap"><span>Отпр. со ст. пр.</span><button type="button" class="col-filter-btn" data-col-index="22">▾</button></div></th>
          <th class="detail-col-arrival" data-col-index="23"><div class="th-wrap"><span>Приб. на ст. назн.</span><button type="button" class="col-filter-btn" data-col-index="23">▾</button></div></th>
          <th class="detail-col-state" data-col-index="24"><div class="th-wrap"><span>Сост. ваг.</span><button type="button" class="col-filter-btn" data-col-index="24">▾</button></div></th>
          <th class="detail-col-owner" data-col-index="25"><div class="th-wrap"><span>Собств.</span><button type="button" class="col-filter-btn" data-col-index="25">▾</button></div></th>
        </tr>
      </thead>
      <tbody>
        {% for item in records %}
        <tr data-detail-row="1">
          <td class="mono">{{ item.wagon_number }}</td>
          <td>{{ item.raw_kind }}</td>
          <td>{{ item.trip_start }}</td>
          <td>{{ item.trip_end }}</td>
          <td>{{ item.origin_road }}</td>
          <td>{{ item.origin_station }}</td>
          <td>{{ item.destination_road }}</td>
          <td>{{ item.destination }}</td>
          <td>{{ item.shipper }}</td>
          <td>{{ item.cargo_name }}</td>
          <td>{{ item.previous_cargo }}</td>
          <td class="num">{{ item.weight_kg }}</td>
          <td>{{ item.station }}</td>
          <td>{{ item.road }}</td>
          <td>{{ item.operation }}</td>
          <td>{{ item.operation_time }}</td>
          <td class="mono">{{ item.train_index }}</td>
          <td>{{ item.container_numbers }}</td>
          <td>{{ item.norm_delivery }}</td>
          <td class="num">{{ item.distance_done }}</td>
          <td class="num">{{ item.distance_left }}</td>
          <td>{{ item.idle_time }}</td>
          <td>{{ item.departure_from_acceptance }}</td>
          <td>{{ item.arrival_destination }}</td>
          <td>{{ item.wagon_state }}</td>
          <td>{{ item.owner }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</section>

<script>
(function(){
  const table = document.getElementById('detail-table');
  if (!table) return;
  const rows = Array.from(table.querySelectorAll('tbody tr[data-detail-row="1"]'));
  const buttons = Array.from(table.querySelectorAll('.col-filter-btn'));
  const clearBtn = document.getElementById('clear-detail-filters');
  const visibleBadge = document.getElementById('visible-count-badge');
  const exportForm = document.getElementById('detail-export-form');
  const filteredRowsInput = document.getElementById('detail-filtered-rows');
  const headers = Array.from(table.querySelectorAll('thead th[data-col-index]')).map(function(th){
    const title = th.querySelector('.th-wrap span');
    return title ? title.textContent.replace(/\\s+/g, ' ').trim() : th.textContent.replace(/\\s+/g, ' ').trim();
  });
  const active = {};
  let popover = null;
  function getCellText(row, colIndex) { const cell = row.children[colIndex]; return cell ? cell.textContent.replace(/\\s+/g, ' ').trim() : ''; }
  function rowMatches(row, excludeKey) { for (const key in active) { if (excludeKey !== undefined && String(key) === String(excludeKey)) continue; const allowed = active[key]; if (!allowed) continue; if (allowed.size === 0) return false; if (!allowed.has(getCellText(row, Number(key)))) return false; } return true; }
  function visibleRowsPayload() {
    return rows.filter(function(row){ return row.style.display !== 'none'; }).map(function(row){
      const item = {};
      headers.forEach(function(header, index){ item[header] = getCellText(row, index); });
      return item;
    });
  }
  function syncExportPayload() {
    if (!filteredRowsInput) return;
    filteredRowsInput.value = JSON.stringify(visibleRowsPayload());
  }
  function applyFilters() {
    let visible = 0; rows.forEach(function(row){ const show = rowMatches(row); row.style.display = show ? '' : 'none'; if (show) visible += 1; }); if (visibleBadge) visibleBadge.textContent = 'Показано: ' + visible; buttons.forEach(function(btn){ const idx = btn.getAttribute('data-col-index'); btn.classList.toggle('is-active', !!(active[idx] !== undefined)); }); syncExportPayload(); }

  function availableValues(colIndex) { const values = new Set(); const key = String(colIndex); rows.forEach(function(row){ if (rowMatches(row, key)) values.add(getCellText(row, colIndex)); }); return Array.from(values).sort(function(a, b){ return a.localeCompare(b, 'ru'); }); }
  function closePopover() { if (popover) { popover.remove(); popover = null; } }
  function positionPopover(button){
    if (!popover) return;
    const rect = button.getBoundingClientRect();
    const margin = 12;
    const width = popover.offsetWidth || 320;
    const height = popover.offsetHeight || 320;
    let left = rect.right - width;
    left = Math.max(margin, Math.min(left, window.innerWidth - width - margin));
    let top = rect.bottom + 8;
    if (top + height > window.innerHeight - margin) top = rect.top - height - 8;
    if (top < margin) top = margin;
    popover.style.top = top + 'px';
    popover.style.left = left + 'px';
  }
  function renderFilterList(list, values, selected, key, query) {
    const q = (query || '').trim().toLowerCase();
    list.innerHTML = '';
    const filtered = values.filter(function(value){ return !q || (value || '').toLowerCase().includes(q); });
    if (!filtered.length) { const empty = document.createElement('div'); empty.className = 'filter-empty'; empty.textContent = 'Нет значений'; list.appendChild(empty); return; }
    filtered.forEach(function(value){
      const label = document.createElement('label'); label.className = 'filter-item';
      const checkbox = document.createElement('input'); checkbox.type = 'checkbox'; checkbox.value = value; checkbox.checked = selected.has(value);
      checkbox.addEventListener('change', function(){ if (checkbox.checked) selected.add(value); else selected.delete(value); active[key] = new Set(selected); applyFilters(); });
      const text = document.createElement('span'); text.textContent = value || 'Пусто';
      label.appendChild(checkbox); label.appendChild(text); list.appendChild(label);
    });
  }
  function openPopover(button, colIndex) {
    closePopover();
    const key = String(colIndex);
    const values = availableValues(colIndex);
    const hasExplicitFilter = active[key] !== undefined;
    const selected = hasExplicitFilter ? new Set(Array.from(active[key]).filter(function(value){ return values.includes(value); })) : new Set(values);
    popover = document.createElement('div');
    popover.className = 'filter-popover';
    const search = document.createElement('input'); search.type = 'search'; search.className = 'search-input'; search.placeholder = 'Поиск'; search.style.marginBottom = '8px';
    popover.appendChild(search);
    const actions = document.createElement('div');
    actions.className = 'filter-actions';
    const btnAll = document.createElement('button'); btnAll.type = 'button'; btnAll.textContent = 'Выбрать все'; btnAll.addEventListener('click', function(){ delete active[key]; applyFilters(); closePopover(); });
    const btnNone = document.createElement('button'); btnNone.type = 'button'; btnNone.textContent = 'Снять все'; btnNone.addEventListener('click', function(){ active[key] = new Set(); applyFilters(); closePopover(); });
    const btnClear = document.createElement('button'); btnClear.type = 'button'; btnClear.textContent = 'Сбросить'; btnClear.addEventListener('click', function(){ delete active[key]; applyFilters(); closePopover(); });
    actions.appendChild(btnAll); actions.appendChild(btnNone); actions.appendChild(btnClear); popover.appendChild(actions);
    const list = document.createElement('div'); list.className = 'filter-list';
    popover.appendChild(list); document.body.appendChild(popover);
    renderFilterList(list, values, selected, key, '');
    search.addEventListener('input', function(){ renderFilterList(list, values, selected, key, search.value); });
    positionPopover(button);
  }
  buttons.forEach(function(button){ button.addEventListener('click', function(event){ event.stopPropagation(); const colIndex = Number(button.getAttribute('data-col-index')); if (popover) closePopover(); openPopover(button, colIndex); }); });
  if (clearBtn) clearBtn.addEventListener('click', function(){ Object.keys(active).forEach(function(key){ delete active[key]; }); applyFilters(); closePopover(); });
  if (exportForm) exportForm.addEventListener('submit', syncExportPayload);
  document.addEventListener('click', function(event){ if (!popover) return; if (popover.contains(event.target)) return; if (event.target.closest('.col-filter-btn')) return; closePopover(); });
  applyFilters();
})();
</script>
{% endif %}
"""

MANUAL_FILTER_BODY = """
<div class="main-tabs">
  <a class="main-tab {% if current_tab == 'approach' %}is-active{% endif %}" href="{{ url_for('index', tab='approach') }}">Подход вагонов</a>
  <a class="main-tab {% if current_tab == 'departure' %}is-active{% endif %}" href="{{ url_for('index', tab='departure') }}">Отправление вагонов</a>
  <a class="main-tab {% if current_tab == 'loading' %}is-active{% endif %}" href="{{ url_for('index', tab='loading') }}">Погрузка</a>
  <a class="main-tab {% if current_tab == 'station_idle' %}is-active{% endif %}" href="{{ url_for('index', tab='station_idle') }}">Простои</a>
  <a class="main-tab {% if current_tab == 'raw_material' %}is-active{% endif %}" href="{{ url_for('index', tab='raw_material') }}">Сырье</a>
  <a class="main-tab {% if current_tab == 'technical_state' %}is-active{% endif %}" href="{{ url_for('technical_state_index') }}">Техническое состояние</a>
  <a class="main-tab is-active" href="{{ url_for('index', tab='manual_filter') }}">Ручной фильтр</a>
  <a class="main-tab" href="{{ url_for('archive_search') }}">Архив</a>
  <a class="main-tab" href="{{ url_for('mailing_rules') }}">Авторассылка справок</a>
</div>

<section class="card topbar">
  <div class="topbar-left">
    <div class="title">{{ app_title }} — Ручной фильтр</div>
    <div class="meta">{{ manual_source_label }}{% if source_name %} • {{ source_name }}{% endif %}{% if source_time %} • {{ source_time }}{% endif %}{% if report_date_label %} • Дата справки: {{ report_date_label }}{% endif %}{% if archive_date %} • Архив: {{ archive_date }}{% endif %}</div>
  </div>
  <div class="topbar-right manual-stats">
    <span class="badge" id="manual-visible-count-badge">Всего: {{ manual_total_count }}</span>
    <span class="badge">Груженые: {{ manual_loaded_count }}</span>
    <span class="badge">Порожние: {{ manual_empty_count }}</span>
  </div>
</section>

{% if error_message %}<div class="error card">{{ error_message }}</div>{% endif %}
{% if success_message %}<div class="success card">{{ success_message }}</div>{% endif %}
{% if manual_message %}<div class="error card">{{ manual_message }}</div>{% endif %}

<div class="manual-layout">
  <section class="card manual-panel">
    <form method="get" action="{{ url_for('index') }}" class="manual-filter-grid">
      <input type="hidden" name="tab" value="manual_filter">
      {% if archive_date %}<input type="hidden" name="archive_date" value="{{ archive_date }}">{% endif %}

      <div class="manual-save-row">
        <div class="manual-field">
          <label class="manual-label" for="saved-filter">Сохранённые фильтры</label>
          <select class="manual-select" id="saved-filter" name="saved_filter">
            <option value="">Не выбран</option>
            {% for item in manual_saved_filters %}
            <option value="{{ item.name }}" {% if item.name == selected_saved_filter %}selected{% endif %}>{{ item.name }}</option>
            {% endfor %}
          </select>
        </div>
        <button class="btn btn-secondary" type="submit" name="load_saved" value="1">Загрузить</button>
        <button class="btn btn-soft" type="submit" formaction="{{ url_for('manual_filters_save') }}" formmethod="post">Сохранить</button>
        <button class="btn btn-secondary" type="submit" formaction="{{ url_for('manual_filters_delete') }}" formmethod="post">Удалить</button>
      </div>

      <div class="manual-field">
        <label class="manual-label" for="manual-filter-name">Название списка</label>
        <input class="manual-text" id="manual-filter-name" type="text" name="manual_filter_name" value="{{ manual_filter_name }}" placeholder="Например: Справка по грузу метанол">
      </div>

      <div class="manual-top-grid">
        <div class="manual-field">
          <label class="manual-label" for="manual-source">Источник данных</label>
          <select class="manual-select" id="manual-source" name="manual_source">
            {% for item in manual_source_options %}
            <option value="{{ item.value }}" {% if item.value == selected_source %}selected{% endif %}>{{ item.label }}</option>
            {% endfor %}
          </select>
        </div>
        <div class="manual-field">
          <label class="manual-label">Действия</label>
          <div class="manual-actions">
            <button class="btn btn-primary" type="submit">Применить</button>
            <a class="btn btn-secondary" id="manual-reset-btn" href="{{ url_for('index', tab='manual_filter', manual_source=selected_source, archive_date=archive_date) }}">Сбросить</a>
            <button class="btn btn-secondary" type="submit" form="manual-export-form">Выгрузить в Excel</button>
          </div>
        </div>
      </div>

      {% for field in manual_fields %}
      {% if field.enabled %}
      <div class="manual-field">
        <label class="manual-label" for="field-{{ field.key }}">{{ field.label }}</label>
        {% if field.kind == 'multi' %}
          <select class="manual-select" id="field-{{ field.key }}" name="{{ field.param }}" multiple size="{{ field.size or 6 }}">
            {% for option in field.options %}
            <option value="{{ option }}" {% if option in field.selected %}selected{% endif %}>{{ option }}</option>
            {% endfor %}
          </select>
        {% elif field.kind == 'single' %}
          <select class="manual-select" id="field-{{ field.key }}" name="{{ field.param }}">
            {% for option in field.options %}
            <option value="{{ option }}" {% if option == field.value %}selected{% endif %}>{{ option }}</option>
            {% endfor %}
          </select>
        {% elif field.kind == 'date' %}
          <input class="manual-text" id="field-{{ field.key }}" type="date" name="{{ field.param }}" value="{{ field.value }}">
        {% else %}
          <input class="manual-text" id="field-{{ field.key }}" type="text" name="{{ field.param }}" value="{{ field.value }}" placeholder="{{ field.placeholder }}" {% if field.datalist_id %}list="{{ field.datalist_id }}"{% endif %} autocomplete="off">
          {% if field.datalist_id %}
          <datalist id="{{ field.datalist_id }}">
            {% for option in field.options %}
            <option value="{{ option }}"></option>
            {% endfor %}
          </datalist>
          {% endif %}
        {% endif %}
      </div>
      {% endif %}
      {% endfor %}

      <div class="manual-source-meta">Фильтры применяются только к выбранному источнику. Для текстовых полей доступны подсказки по мере ввода. Если в поле выбрано «Все», ограничение по нему не применяется.</div>
    </form>
    <form method="post" action="{{ manual_export_url }}" id="manual-export-form" style="display:none;">
      <input type="hidden" name="filtered_rows" id="manual-filtered-rows" value="">
    </form>
  </section>

  <section class="card manual-panel">
    <div class="toolbar" style="margin:-12px -12px 12px -12px;">
      <div>
        <div class="toolbar-title">Результат ручного фильтра</div>
        <div class="toolbar-sub">{{ manual_source_label }}</div>
      </div>
    </div>

    {% if manual_active_filters %}
    <div class="manual-active">
      {% for item in manual_active_filters %}
      <span class="manual-chip">
        <span>{{ item.text }}</span>
        {% if item.remove_url %}<a class="manual-chip-remove" href="{{ item.remove_url }}" title="Снять фильтр">×</a>{% endif %}
      </span>
      {% endfor %}
    </div>
    {% else %}
    <div class="manual-source-meta">Активные фильтры не заданы.</div>
    {% endif %}

    {% if manual_records %}
    <div class="table-wrap">
      <table class="manual-table" id="manual-result-table">
        <thead>
          <tr>
            <th class="manual-col-wagon" data-manual-col-index="0"><div class="manual-th-wrap"><span class="manual-th-title">№ вагона</span><span class="manual-th-actions"><button type="button" class="manual-col-filter-btn" data-manual-col-index="0">▾</button><button type="button" class="manual-col-hide-btn" data-manual-col-index="0">✕</button></span></div></th>
            <th class="manual-col-kind" data-manual-col-index="1"><div class="manual-th-wrap"><span class="manual-th-title">Род вагона</span><span class="manual-th-actions"><button type="button" class="manual-col-filter-btn" data-manual-col-index="1">▾</button><button type="button" class="manual-col-hide-btn" data-manual-col-index="1">✕</button></span></div></th>
            <th class="manual-col-state" data-manual-col-index="2"><div class="manual-th-wrap"><span class="manual-th-title">Состояние</span><span class="manual-th-actions"><button type="button" class="manual-col-filter-btn" data-manual-col-index="2">▾</button><button type="button" class="manual-col-hide-btn" data-manual-col-index="2">✕</button></span></div></th>
            <th class="manual-col-owner" data-manual-col-index="3"><div class="manual-th-wrap"><span class="manual-th-title">Собственник</span><span class="manual-th-actions"><button type="button" class="manual-col-filter-btn" data-manual-col-index="3">▾</button><button type="button" class="manual-col-hide-btn" data-manual-col-index="3">✕</button></span></div></th>
            <th class="manual-col-cargo" data-manual-col-index="4"><div class="manual-th-wrap"><span class="manual-th-title">Груз</span><span class="manual-th-actions"><button type="button" class="manual-col-filter-btn" data-manual-col-index="4">▾</button><button type="button" class="manual-col-hide-btn" data-manual-col-index="4">✕</button></span></div></th>
            <th class="manual-col-shipper" data-manual-col-index="5"><div class="manual-th-wrap"><span class="manual-th-title">Грузоотправитель</span><span class="manual-th-actions"><button type="button" class="manual-col-filter-btn" data-manual-col-index="5">▾</button><button type="button" class="manual-col-hide-btn" data-manual-col-index="5">✕</button></span></div></th>
            <th class="manual-col-consignee" data-manual-col-index="6"><div class="manual-th-wrap"><span class="manual-th-title">Грузополучатель</span><span class="manual-th-actions"><button type="button" class="manual-col-filter-btn" data-manual-col-index="6">▾</button><button type="button" class="manual-col-hide-btn" data-manual-col-index="6">✕</button></span></div></th>
            <th class="manual-col-origin-station" data-manual-col-index="7"><div class="manual-th-wrap"><span class="manual-th-title">Станция отправления</span><span class="manual-th-actions"><button type="button" class="manual-col-filter-btn" data-manual-col-index="7">▾</button><button type="button" class="manual-col-hide-btn" data-manual-col-index="7">✕</button></span></div></th>
            <th class="manual-col-origin-road" data-manual-col-index="8"><div class="manual-th-wrap"><span class="manual-th-title">Дорога отправления</span><span class="manual-th-actions"><button type="button" class="manual-col-filter-btn" data-manual-col-index="8">▾</button><button type="button" class="manual-col-hide-btn" data-manual-col-index="8">✕</button></span></div></th>
            <th class="manual-col-destination-station" data-manual-col-index="9"><div class="manual-th-wrap"><span class="manual-th-title">Станция назначения</span><span class="manual-th-actions"><button type="button" class="manual-col-filter-btn" data-manual-col-index="9">▾</button><button type="button" class="manual-col-hide-btn" data-manual-col-index="9">✕</button></span></div></th>
            <th class="manual-col-destination-road" data-manual-col-index="10"><div class="manual-th-wrap"><span class="manual-th-title">Дорога назначения</span><span class="manual-th-actions"><button type="button" class="manual-col-filter-btn" data-manual-col-index="10">▾</button><button type="button" class="manual-col-hide-btn" data-manual-col-index="10">✕</button></span></div></th>
            <th class="manual-col-operation-station" data-manual-col-index="11"><div class="manual-th-wrap"><span class="manual-th-title">Станция операции</span><span class="manual-th-actions"><button type="button" class="manual-col-filter-btn" data-manual-col-index="11">▾</button><button type="button" class="manual-col-hide-btn" data-manual-col-index="11">✕</button></span></div></th>
            <th class="manual-col-operation-road" data-manual-col-index="12"><div class="manual-th-wrap"><span class="manual-th-title">Дорога операции</span><span class="manual-th-actions"><button type="button" class="manual-col-filter-btn" data-manual-col-index="12">▾</button><button type="button" class="manual-col-hide-btn" data-manual-col-index="12">✕</button></span></div></th>
            <th class="manual-col-operation" data-manual-col-index="13"><div class="manual-th-wrap"><span class="manual-th-title">Операция</span><span class="manual-th-actions"><button type="button" class="manual-col-filter-btn" data-manual-col-index="13">▾</button><button type="button" class="manual-col-hide-btn" data-manual-col-index="13">✕</button></span></div></th>
            <th class="manual-col-operation-time" data-manual-col-index="14"><div class="manual-th-wrap"><span class="manual-th-title">Дата операции</span><span class="manual-th-actions"><button type="button" class="manual-col-filter-btn" data-manual-col-index="14">▾</button><button type="button" class="manual-col-hide-btn" data-manual-col-index="14">✕</button></span></div></th>
            <th class="manual-col-operation-time" data-manual-col-index="15"><div class="manual-th-wrap"><span class="manual-th-title">Дата и время окончания рейса</span><span class="manual-th-actions"><button type="button" class="manual-col-filter-btn" data-manual-col-index="15">▾</button><button type="button" class="manual-col-hide-btn" data-manual-col-index="15">✕</button></span></div></th>
          </tr>
        </thead>
        <tbody>
          {% for item in manual_records %}
          <tr>
            <td class="mono manual-cell-wagon" data-manual-col-index="0">{{ item.wagon_number }}</td>
            <td data-manual-col-index="1">{{ item.raw_kind }}</td>
            <td data-manual-col-index="2">{{ item.cargo_state }}</td>
            <td data-manual-col-index="3">{{ item.owner }}</td>
            <td data-manual-col-index="4">{{ item.cargo_name }}</td>
            <td data-manual-col-index="5">{{ item.shipper }}</td>
            <td data-manual-col-index="6">{{ item.consignee }}</td>
            <td data-manual-col-index="7">{{ item.origin_station }}</td>
            <td data-manual-col-index="8">{{ item.origin_road }}</td>
            <td data-manual-col-index="9">{{ item.destination }}</td>
            <td data-manual-col-index="10">{{ item.destination_road }}</td>
            <td data-manual-col-index="11">{{ item.station }}</td>
            <td data-manual-col-index="12">{{ item.road }}</td>
            <td data-manual-col-index="13">{{ item.operation }}</td>
            <td data-manual-col-index="14">{{ item.operation_time }}</td>
            <td data-manual-col-index="15">{{ item.trip_end }}</td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
    <script>
    (function(){
      const table = document.getElementById('manual-result-table');
      if (!table) return;
      const clearLink = document.getElementById('manual-reset-btn');
      const visibleBadge = document.getElementById('manual-visible-count-badge');
      const headers = Array.from(table.querySelectorAll('thead th[data-manual-col-index]'));
      const rows = Array.from(table.querySelectorAll('tbody tr'));
      const filterButtons = Array.from(table.querySelectorAll('.manual-col-filter-btn'));
      const hideButtons = Array.from(table.querySelectorAll('.manual-col-hide-btn'));
      const exportForm = document.getElementById('manual-export-form');
      const filteredRowsInput = document.getElementById('manual-filtered-rows');
      let popover = null;
      const active = {};
      const hiddenCols = new Set();

      function closePopover(){
        if (popover && popover.parentNode) popover.parentNode.removeChild(popover);
        popover = null;
      }

      function cellText(row, colIndex){
        const cell = row.querySelector('td[data-manual-col-index="' + colIndex + '"]');
        return cell ? cell.textContent.trim() : '';
      }

      function updateVisibleCount(){
        if (!visibleBadge) return;
        const count = rows.filter(function(row){ return row.style.display !== 'none'; }).length;
        visibleBadge.textContent = 'Всего строк: ' + count;
      }

      function applyColumnVisibility(){
        headers.forEach(function(th){
          const index = Number(th.getAttribute('data-manual-col-index'));
          th.classList.toggle('is-hidden', hiddenCols.has(index));
        });
        rows.forEach(function(row){
          Array.from(row.querySelectorAll('td[data-manual-col-index]')).forEach(function(td){
            const index = Number(td.getAttribute('data-manual-col-index'));
            td.classList.toggle('is-hidden', hiddenCols.has(index));
          });
        });
      }

      function visibleRowsPayload(){
        return rows.filter(function(row){ return row.style.display !== 'none'; }).map(function(row){
          const item = {};
          headers.forEach(function(th){
            const index = Number(th.getAttribute('data-manual-col-index'));
            const titleNode = th.querySelector('.manual-th-title');
            const header = titleNode ? titleNode.textContent.trim() : th.textContent.trim();
            item[header] = cellText(row, index);
          });
          return item;
        });
      }

      function syncManualExportPayload(){
        if (!filteredRowsInput) return;
        filteredRowsInput.value = JSON.stringify(visibleRowsPayload());
      }

      function rowMatches(row, excludeKey){
        let visible = true;
        Object.keys(active).forEach(function(key){
          if (!visible) return;
          if (excludeKey !== undefined && String(key) === String(excludeKey)) return;
          const selected = active[key];
          if (!selected || !selected.size) return;
          const value = cellText(row, key);
          if (!selected.has(value || 'Пусто')) visible = false;
        });
        return visible;
      }

      function applyFilters(){
        rows.forEach(function(row){
          row.style.display = rowMatches(row) ? '' : 'none';
        });
        filterButtons.forEach(function(btn){
          const idx = btn.getAttribute('data-manual-col-index');
          btn.classList.toggle('is-active', !!(active[idx] && active[idx].size));
        });
        applyColumnVisibility();
        updateVisibleCount();
        syncManualExportPayload();
      }

      function allValues(colIndex){
        const values = new Set();
        const key = String(colIndex);
        rows.forEach(function(row){ if (rowMatches(row, key)) values.add(cellText(row, colIndex) || 'Пусто'); });
        return Array.from(values).sort(function(a, b){ return a.localeCompare(b, 'ru'); });
      }

      function positionManualPopover(button){
        if (!popover) return;
        const rect = button.getBoundingClientRect();
        const margin = 12;
        const width = popover.offsetWidth || 320;
        const height = popover.offsetHeight || 320;
        let left = rect.right - width;
        left = Math.max(margin, Math.min(left, window.innerWidth - width - margin));
        let top = rect.bottom + 8;
        if (top + height > window.innerHeight - margin) top = rect.top - height - 8;
        if (top < margin) top = margin;
        popover.style.top = top + 'px';
        popover.style.left = left + 'px';
      }
      function renderManualFilterList(list, values, selected, colIndex, query){
        const q = (query || '').trim().toLowerCase();
        list.innerHTML = '';
        const filtered = values.filter(function(value){ return !q || String(value).toLowerCase().includes(q); });
        if (!filtered.length){
          const empty = document.createElement('div');
          empty.className = 'manual-filter-empty';
          empty.textContent = 'Нет значений для фильтрации.';
          list.appendChild(empty);
          return;
        }
        filtered.forEach(function(value){
          const label = document.createElement('label');
          label.className = 'manual-filter-item';
          const checkbox = document.createElement('input');
          checkbox.type = 'checkbox';
          checkbox.checked = selected.has(value);
          checkbox.addEventListener('change', function(){
            if (checkbox.checked) selected.add(value); else selected.delete(value);
            if (selected.size) active[colIndex] = new Set(selected); else delete active[colIndex];
            applyFilters();
          });
          const text = document.createElement('span');
          text.textContent = value;
          label.appendChild(checkbox); label.appendChild(text); list.appendChild(label);
        });
      }
      function openPopover(button, colIndex){
        popover = document.createElement('div');
        popover.className = 'manual-filter-popover';
        const selected = active[colIndex] ? new Set(active[colIndex]) : new Set();

        const search = document.createElement('input');
        search.type = 'search';
        search.className = 'search-input';
        search.placeholder = 'Поиск';
        search.style.marginBottom = '8px';
        popover.appendChild(search);

        const actions = document.createElement('div');
        actions.className = 'manual-filter-actions';
        const allBtn = document.createElement('button');
        allBtn.type = 'button';
        allBtn.textContent = 'Выбрать все';
        const clearBtn = document.createElement('button');
        clearBtn.type = 'button';
        clearBtn.textContent = 'Очистить';
        actions.appendChild(allBtn); actions.appendChild(clearBtn);
        popover.appendChild(actions);

        const values = allValues(colIndex);
        const list = document.createElement('div');
        list.className = 'manual-filter-list';
        popover.appendChild(list);
        renderManualFilterList(list, values, selected, colIndex, '');
        search.addEventListener('input', function(){ renderManualFilterList(list, values, selected, colIndex, search.value); });

        if (values.length){
          allBtn.addEventListener('click', function(){
            selected.clear(); values.forEach(function(value){ selected.add(value); });
            active[colIndex] = new Set(selected); closePopover(); applyFilters();
          });
        }
        clearBtn.addEventListener('click', function(){ delete active[colIndex]; closePopover(); applyFilters(); });
        document.body.appendChild(popover);
        positionManualPopover(button);
      }

      filterButtons.forEach(function(button){
        button.addEventListener('click', function(event){
          event.stopPropagation();
          const colIndex = button.getAttribute('data-manual-col-index');
          if (popover) closePopover();
          openPopover(button, colIndex);
        });
      });

      hideButtons.forEach(function(button){
        button.addEventListener('click', function(event){
          event.preventDefault();
          event.stopPropagation();
          const colIndex = Number(button.getAttribute('data-manual-col-index'));
          hiddenCols.add(colIndex);
          closePopover();
          applyFilters();
        });
      });

      if (clearLink){
        clearLink.addEventListener('click', function(){
          Object.keys(active).forEach(function(key){ delete active[key]; });
          hiddenCols.clear();
          closePopover();
        });
      }

      document.addEventListener('click', function(event){
        if (!popover) return;
        if (popover.contains(event.target)) return;
        if (event.target.closest('.manual-col-filter-btn')) return;
        closePopover();
      });

      if (exportForm){
        exportForm.addEventListener('submit', syncManualExportPayload);
      }

      applyFilters();
    })();
    </script>
    {% else %}
    <div class="manual-empty">По заданным условиям ничего не найдено.</div>
    {% endif %}
  </section>
</div>
"""

STOP_RENT_BODY = """
<div class="breadcrumb">
  <a href="{{ url_for('index', tab=current_tab, archive_date=archive_date, idle_view=station_idle_mode if current_tab == 'station_idle' else None) }}">Назад к сводке</a>
  <span>•</span>
  <span>Стоп аренда</span>
  {% if archive_date %}<span>• Архив: {{ archive_date }}</span>{% endif %}
</div>

{% if success_message %}<div class="success card">{{ success_message }}</div>{% endif %}
{% if error_message %}<div class="error card">{{ error_message }}</div>{% endif %}

<section class="card detail-head">
  <div>
    <h1 class="detail-title">Стоп аренда</h1>
    <div class="toolbar-sub">Видимые группы по состоянию на дату справки{% if archive_date %} (архив){% endif %}</div>
  </div>
  <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
    <a class="btn btn-soft" href="{{ url_for('stop_rent_password', tab=current_tab, archive_date=archive_date) }}">Сменить пароль</a>
    <div class="chips">
    {% if archive_date %}<span class="chip">Архив: {{ archive_date }}</span>{% endif %}
    <span class="chip">Всего групп: {{ stop_rent_groups|length }}</span>
    <span class="chip">Всего вагонов: {{ stop_rent_total_count }}</span>
  </div>
  </div>
</section>

<section class="card table-card" style="padding:12px; margin-bottom:12px;">
  <div class="toolbar" style="margin:-12px -12px 12px -12px;">
    <div>
      <div class="toolbar-title">Выбор станции</div>
      <div class="toolbar-sub">Выберите станцию и отметьте вагоны для запуска стоп аренды</div>
    </div>
  </div>
  {% if station_options %}
  <div class="station-picker">
    {% for item in station_options %}
      <a class="station-link" href="{{ url_for('stop_rent', tab=current_tab, station=item.name, archive_date=archive_date, batch=batch_id) }}">{{ item.name }} <span class="mini-muted">({{ item.count }})</span></a>
    {% endfor %}
  </div>
  {% else %}
  <div class="empty">Нет доступных станций для выбора.</div>
  {% endif %}
</section>

<div class="stop-grid">
  <section class="card table-card" style="padding:12px;">
    <div class="toolbar" style="margin:-12px -12px 12px -12px;">
      <div>
        <div class="toolbar-title">Запуск стоп аренды{% if selected_station %}: {{ selected_station }}{% endif %}</div>
        <div class="toolbar-sub">Выберите вагоны и укажите дату начала</div>
      </div>
    </div>
    {% if selected_station and station_records %}
    <form method="post" action="{{ url_for('stop_rent_create') }}">
      <input type="hidden" name="tab" value="{{ current_tab }}">
      <input type="hidden" name="station" value="{{ selected_station }}">
      {% if archive_date %}<input type="hidden" name="archive_date" value="{{ archive_date }}">{% endif %}
      <div class="selection-tools">
        <button class="btn btn-ghost" type="button" id="select-all-wagons">Выбрать все</button>
        <button class="btn btn-ghost" type="button" id="clear-all-wagons">Снять выделение</button>
        <label class="form-row">
          <span class="mini-muted">Дата начала:</span>
          <input class="input" type="date" name="start_date" value="{{ default_start_date }}" required>
        </label>
        <button class="btn btn-primary" type="submit">Сохранить</button>
      </div>
      <div class="selection-box">
        <table class="selection-table" id="wagon-selection-table">
          <thead>
            <tr>
              <th class="selection-col-check"></th>
              <th class="selection-col-wagon">№ вагона</th>
              <th class="selection-col-kind">Род вагона</th>
              <th class="selection-col-op">Операция</th>
              <th class="selection-col-time">Дата/время операции</th>
            </tr>
          </thead>
          <tbody>
            {% for row in station_records %}
            <tr>
              <td><input type="checkbox" name="wagon_numbers" value="{{ row.wagon_number }}"></td>
              <td class="mono">{{ row.wagon_number }}</td>
              <td>{{ row.raw_kind }}</td>
              <td>{{ row.operation }}</td>
              <td>{{ row.operation_time }}</td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    </form>
    <script>
    (function(){
      const table = document.getElementById('wagon-selection-table');
      if (!table) return;
      const boxes = Array.from(table.querySelectorAll('input[type="checkbox"][name="wagon_numbers"]'));
      const selectBtn = document.getElementById('select-all-wagons');
      const clearBtn = document.getElementById('clear-all-wagons');
      if (selectBtn) selectBtn.addEventListener('click', function(){ boxes.forEach(box => box.checked = true); });
      if (clearBtn) clearBtn.addEventListener('click', function(){ boxes.forEach(box => box.checked = false); });
    })();
    </script>
    {% elif selected_station %}
    <div class="empty">По выбранной станции не найдено вагонов.</div>
    {% else %}
    <div class="empty">Сначала выберите станцию.</div>
    {% endif %}
  </section>

  <section class="card table-card" style="padding:12px;">
    <div class="toolbar" style="margin:-12px -12px 12px -12px;">
      <div>
        <div class="toolbar-title">Действующие и недавние стоп аренды</div>
        <div class="toolbar-sub">После окончания запись отображается ещё 3 суток</div>
      </div>
    </div>
    {% if stop_rent_groups %}
      <div class="stop-group-list">
        {% for group in stop_rent_groups %}
        <div class="stop-group-item">
          <a class="stop-group-link" href="{{ url_for('stop_rent', tab=current_tab, archive_date=archive_date, batch=group.batch_id, station=selected_station) }}">
            <span>{{ group.title }}</span>
            <span class="chip">{{ group.count }} ваг.</span>
          </a>
          <div class="stop-group-meta">{{ group.station_names }} • {{ group.status_summary }}</div>
        </div>
        {% endfor %}
      </div>
    {% else %}
    <div class="empty">Нет активных или недавних записей по стоп аренде.</div>
    {% endif %}

    {% if selected_group %}
    <div style="height:12px;"></div>
    <div class="toolbar" style="margin:0 -12px 12px -12px;">
      <div>
        <div class="toolbar-title">{{ selected_group.title }}</div>
        <div class="toolbar-sub">{{ selected_group.station_names }} • {{ selected_group.status_summary }}</div>
      </div>
      <div class="toolbar-right">
        {% if not archive_date %}
        <form method="post" action="{{ url_for('stop_rent_delete_batch') }}" onsubmit="return confirm('Удалить всю группу стоп аренды?');">
          <input type="hidden" name="tab" value="{{ current_tab }}">
          <input type="hidden" name="batch_id" value="{{ selected_group.batch_id }}">
          <button class="btn btn-secondary" type="submit">Удалить группу</button>
        </form>
        {% endif %}
      </div>
    </div>
    <div class="stop-table-wrap">
      <form method="post" action="{{ url_for('stop_rent_delete_selected') }}">
        <input type="hidden" name="tab" value="{{ current_tab }}">
        <input type="hidden" name="batch_id" value="{{ selected_group.batch_id }}">
        <div class="stop-actions">
          {% if not archive_date %}
          <button class="btn btn-ghost" type="button" id="select-all-stop-group">Выбрать все</button>
          <button class="btn btn-ghost" type="button" id="clear-all-stop-group">Снять выделение</button>
          <button class="btn btn-secondary" type="submit">Удалить выбранные вагоны</button>
          {% else %}<span class="mini-muted">В архивном режиме удаление недоступно.</span>{% endif %}
        </div>
        <table class="stop-detail-table" id="stop-group-table">
          <thead>
            <tr>
              {% if not archive_date %}<th class="stop-col-check"></th>{% endif %}
              <th class="stop-col-wagon">№ вагона</th>
              <th class="stop-col-kind">Род вагона</th>
              <th class="stop-col-op">Операция</th>
              <th class="stop-col-time">Дата/время операции</th>
              <th class="stop-col-start">Начало</th>
              <th class="stop-col-end">Окончание</th>
              <th class="stop-col-days">Суток</th>
              <th class="stop-col-status">Статус</th>
            </tr>
          </thead>
          <tbody>
            {% for row in selected_group.records %}
            <tr>
              {% if not archive_date %}<td><input type="checkbox" name="wagon_numbers" value="{{ row.wagon_number }}"></td>{% endif %}
              <td class="mono">{{ row.wagon_number }}</td>
              <td>{{ row.raw_kind }}</td>
              <td>{{ row.operation }}</td>
              <td>{{ row.operation_time }}</td>
              <td>{{ row.start_date }}</td>
              <td>{{ row.end_date or "—" }}</td>
              <td>{{ row.days_display }}</td>
              <td>{{ row.status_label }}</td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </form>
    </div>
    <script>
    (function(){
      const table = document.getElementById('stop-group-table');
      if (!table) return;
      const boxes = Array.from(table.querySelectorAll('input[type="checkbox"][name="wagon_numbers"]'));
      const selectBtn = document.getElementById('select-all-stop-group');
      const clearBtn = document.getElementById('clear-all-stop-group');
      if (selectBtn) selectBtn.addEventListener('click', function(){ boxes.forEach(box => box.checked = true); });
      if (clearBtn) clearBtn.addEventListener('click', function(){ boxes.forEach(box => box.checked = false); });
    })();
    </script>
    {% endif %}
  </section>
</div>
"""


ACTIVATION_BODY = """
<section class="activation-layout">
  <section class="card activation-card">
    <div class="activation-title">Активация приложения</div>
    <div class="activation-sub">
      {{ activation_help_text }}
      {% if app_version %}<div class="mini-note">Текущая версия приложения: {{ app_version }}</div>{% endif %}
    </div>

    <div class="activation-grid">
      <div class="activation-box">
        <div class="activation-box-title">Код устройства</div>
        <div class="activation-code" id="device-code">{{ device_code }}</div>
        <div class="activation-actions">
          <button class="btn btn-primary" type="button" id="copy-device-code-btn">Скопировать код</button>
          <a class="btn btn-soft" href="{{ url_for('license_request_download') }}">Сохранить запрос</a>
          {% if local_license_path %}<span class="badge">{{ local_license_path }}</span>{% endif %}
        </div>
        <div class="mini-note">Сохрани файл запроса и отправь его администратору. Он откроет его в админ-утилите и выпустит лицензию без ручного ввода кода устройства.</div>
      </div>

      <div class="activation-box">
        <div class="activation-box-title">Сведения об устройстве</div>
        <div class="activation-kv">
          <div class="activation-kv-row"><div class="activation-kv-label">Компьютер</div><div class="activation-kv-value">{{ device_name }}</div></div>
          <div class="activation-kv-row"><div class="activation-kv-label">Пользователь Windows</div><div class="activation-kv-value">{{ os_user }}</div></div>
          <div class="activation-kv-row"><div class="activation-kv-label">Каталог лицензии</div><div class="activation-kv-value">{{ storage_dir }}</div></div>
        </div>
      </div>

      <div class="activation-box">
        <div class="activation-box-title">Статус лицензии</div>
        <div class="license-status {% if license_active %}ok{% else %}bad{% endif %}">
          {% if license_active %}Лицензия активна{% else %}Лицензия не активна{% endif %}
        </div>
        <div class="activation-help" style="margin-top: 10px;">{{ license_reason }}</div>

        {% if license_payload %}
        <div class="activation-kv">
          <div class="activation-kv-row"><div class="activation-kv-label">Лицензия</div><div class="activation-kv-value">{{ license_payload.license_id or "—" }}</div></div>
          <div class="activation-kv-row"><div class="activation-kv-label">Пользователь</div><div class="activation-kv-value">{{ license_payload.user or "—" }}</div></div>
          <div class="activation-kv-row"><div class="activation-kv-label">Срок действия</div><div class="activation-kv-value">{{ license_payload.expires_at or "Без ограничения" }}</div></div>
        </div>
        {% endif %}
      </div>
    </div>
  </section>

  <section class="card activation-card">
    <div class="activation-title">Загрузка лицензии</div>
    <div class="activation-sub">Загрузите файл лицензии (*.lic), который администратор выпустил по вашему файлу запроса и именно под этот компьютер.</div>

    <form class="activation-form" method="post" action="{{ url_for('license_upload') }}" enctype="multipart/form-data">
      {% if next_url %}<input type="hidden" name="next" value="{{ next_url }}">{% endif %}
      <label class="file-label" style="width: fit-content;">
        <span>Выбрать файл лицензии</span>
        <input type="file" name="license_file" accept=".lic,.json" required>
      </label>
      <div class="activation-actions">
        <button class="btn btn-primary" type="submit">Активировать</button>
        {% if license_payload %}<a class="btn btn-secondary" href="{{ url_for('license_remove') }}">Удалить текущую лицензию</a>{% endif %}
        {% if next_url and license_active %}<a class="btn btn-soft" href="{{ next_url }}">Перейти в приложение</a>{% endif %}
      </div>
    </form>

    {% if update_info %}
    <div class="activation-box update-box" style="margin-top: 14px;">
      <div class="activation-box-title">Обновление</div>
      {% if update_info.has_update %}
        <div class="license-status warn">Доступна новая версия {{ update_info.latest_version }}</div>
        {% if update_info.notes %}
        <ul class="update-list">
          {% for line in update_info.notes %}
          <li>{{ line }}</li>
          {% endfor %}
        </ul>
        {% endif %}
        {% if update_info.installer_url %}
        <div class="activation-actions">
          <a class="btn btn-primary" href="{{ url_for('open_update_installer') }}">Установить обновление</a>
        </div>
        {% endif %}
      {% else %}
        <div class="license-status ok">Установлена актуальная версия</div>
      {% endif %}
      {% if update_info.source_error %}<div class="mini-note">Проверка облака: {{ update_info.source_error }}</div>{% endif %}
    </div>
    {% endif %}

    <div class="activation-box" style="margin-top: 14px;">
      <div class="activation-box-title">Подсказка</div>
      <div class="activation-help">
        1. Скопируйте код устройства.<br>
        2. Передайте его администратору.<br>
        3. Получите файл лицензии и загрузите его в это окно.
      </div>
    </div>
  </section>
</section>

{% if success_message %}<div class="success card">{{ success_message }}</div>{% endif %}
{% if error_message %}<div class="error card">{{ error_message }}</div>{% endif %}

<script>
(function(){
  const copyBtn = document.getElementById('copy-device-code-btn');
  const codeEl = document.getElementById('device-code');
  if (!copyBtn || !codeEl) return;
  copyBtn.addEventListener('click', async function(){
    const text = codeEl.textContent.trim();
    try {
      await navigator.clipboard.writeText(text);
      copyBtn.textContent = 'Скопировано';
      setTimeout(function(){ copyBtn.textContent = 'Скопировать код'; }, 1600);
    } catch(e) {
      window.prompt('Скопируйте код вручную:', text);
    }
  });
})();
</script>
"""



STOP_RENT_ACCESS_BODY = """
<div class="breadcrumb">
  <a href="{{ url_for('index', tab=current_tab, archive_date=archive_date, idle_view=station_idle_mode if current_tab == 'station_idle' else None) }}">Назад к сводке</a>
  <span>•</span>
  <span>Стоп аренда</span>
</div>

{% if success_message %}<div class="success card">{{ success_message }}</div>{% endif %}
{% if error_message %}<div class="error card">{{ error_message }}</div>{% endif %}

<section class="card" style="max-width:640px; margin:0 auto; padding:18px;">
  <div class="toolbar" style="margin:-18px -18px 14px -18px;">
    <div>
      <div class="toolbar-title">Доступ к разделу «Стоп аренда»</div>
      <div class="toolbar-sub">Пароль требуется при каждом переходе в раздел</div>
    </div>
  </div>
  <form method="post" action="{{ url_for('stop_rent_access', tab=current_tab, archive_date=archive_date) }}" style="display:grid; gap:12px;">
    <label class="form-row">
      <span class="mini-muted">Пароль</span>
      <input class="input" type="password" name="password" autocomplete="current-password" required>
    </label>
    <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
      <button class="btn btn-primary" type="submit">Войти</button>
      <span class="badge">Ошибок подряд: {{ failed_attempts }}</span>
      {% if show_reset_button %}<button class="btn btn-secondary" type="submit" formaction="{{ url_for('stop_rent_reset_request', tab=current_tab, archive_date=archive_date) }}" formnovalidate>Сбросить пароль</button>{% endif %}
    </div>
  </form>

  {% if request_code %}
  <div class="card" style="margin-top:14px; padding:14px; background:#f8fbff; border:1px solid #dce4ee;">
    <div class="toolbar-title" style="font-size:15px;">Код запроса</div>
    <div class="mono" style="margin-top:8px; font-size:18px; word-break:break-all;">{{ request_code }}</div>
    <div class="toolbar-sub" style="margin-top:8px;">Передайте код администратору. После получения кода восстановления введите его ниже и задайте новый пароль.</div>
    <form method="post" action="{{ url_for('stop_rent_reset_confirm', tab=current_tab, archive_date=archive_date) }}" style="display:grid; gap:12px; margin-top:14px;">
      <label class="form-row">
        <span class="mini-muted">Код восстановления</span>
        <input class="input" type="text" name="recovery_code" autocomplete="off" required>
      </label>
      <label class="form-row">
        <span class="mini-muted">Новый пароль</span>
        <input class="input" type="password" name="new_password" autocomplete="new-password" required>
      </label>
      <label class="form-row">
        <span class="mini-muted">Повторите пароль</span>
        <input class="input" type="password" name="new_password_confirm" autocomplete="new-password" required>
      </label>
      <div><button class="btn btn-primary" type="submit">Подтвердить сброс</button></div>
    </form>
  </div>
  {% endif %}
</section>
"""

STOP_RENT_PASSWORD_BODY = """
<div class="breadcrumb">
  <a href="{{ url_for('stop_rent', tab=current_tab, archive_date=archive_date) }}">← Назад к стоп аренде</a>
  <span>•</span>
  <span>Сменить пароль</span>
</div>

{% if success_message %}<div class="success card">{{ success_message }}</div>{% endif %}
{% if error_message %}<div class="error card">{{ error_message }}</div>{% endif %}

<section class="card" style="max-width:640px; margin:0 auto; padding:18px;">
  <div class="toolbar" style="margin:-18px -18px 14px -18px;">
    <div>
      <div class="toolbar-title">Сменить пароль раздела «Стоп аренда»</div>
      <div class="toolbar-sub">Стартовый пароль: 1234</div>
    </div>
  </div>
  <form method="post" action="{{ url_for('stop_rent_password', tab=current_tab, archive_date=archive_date) }}" style="display:grid; gap:12px;">
    <label class="form-row">
      <span class="mini-muted">Текущий пароль</span>
      <input class="input" type="password" name="current_password" autocomplete="current-password" required>
    </label>
    <label class="form-row">
      <span class="mini-muted">Новый пароль</span>
      <input class="input" type="password" name="new_password" autocomplete="new-password" required>
    </label>
    <label class="form-row">
      <span class="mini-muted">Повторите новый пароль</span>
      <input class="input" type="password" name="new_password_confirm" autocomplete="new-password" required>
    </label>
    <div><button class="btn btn-primary" type="submit">Сохранить новый пароль</button></div>
  </form>
</section>
"""


MAILING_BODY = """
<div class="main-tabs">
  <a class="main-tab" href="{{ url_for('index', tab='approach') }}">Подход вагонов</a>
  <a class="main-tab" href="{{ url_for('index', tab='departure') }}">Отправление вагонов</a>
  <a class="main-tab" href="{{ url_for('index', tab='loading') }}">Погрузка</a>
  <a class="main-tab" href="{{ url_for('index', tab='station_idle') }}">Простои</a>
  <a class="main-tab" href="{{ url_for('index', tab='manual_filter') }}">Ручной фильтр</a>
  <a class="main-tab" href="{{ url_for('archive_search') }}">Архив</a>
  <a class="main-tab is-active" href="{{ url_for('mailing_rules') }}">Авторассылка справок</a>
</div>

{% if error_message %}<div class="error">{{ error_message }}</div>{% endif %}
{% if success_message %}<div class="success">{{ success_message }}</div>{% endif %}

<section class="card table-card">
  <div class="toolbar">
    <div>
      <div class="toolbar-title">Авторассылка справок</div>
      <div class="toolbar-sub">Настройка правил автоматической отправки Excel-справок через Outlook</div>
    </div>
    <div class="toolbar-right">
      <a class="btn btn-primary" href="{{ url_for('mailing_new') }}">Добавить</a>
      <a class="btn btn-soft" href="{{ url_for('mailing_logs') }}">Журнал</a>
    </div>
  </div>
  <div class="table-wrap">
    <table class="mailing-table">
      <thead>
        <tr>
          <th class="mailing-col-enabled">Активна</th>
          <th class="mailing-col-name">Название</th>
          <th class="mailing-col-report">Справка</th>
          <th class="mailing-col-recipients">Получатели</th>
          <th class="mailing-col-schedule">Расписание</th>
          <th class="mailing-col-last-run">Последняя отправка</th>
          <th class="mailing-col-status">Последний статус</th>
          <th class="mailing-col-actions">Действия</th>
        </tr>
      </thead>
      <tbody>
        {% if rules %}
          {% for rule in rules %}
          <tr>
            <td><span class="mailing-cell-wrap">{{ 'Да' if rule.enabled else 'Нет' }}</span></td>
            <td><span class="mailing-cell-wrap">{{ rule.name }}</span></td>
            <td><span class="mailing-cell-wrap">{{ report_labels.get(rule.report_type, rule.report_type) }}</span></td>
            <td><span class="mailing-cell-wrap">{{ rule.to }}</span></td>
            <td><span class="mailing-cell-wrap">{{ schedule_map.get(rule.id, '—') }}</span></td>
            <td><span class="mailing-cell-wrap">{{ rule.last_run_at or '—' }}</span></td>
            <td><span class="mailing-cell-wrap">{{ rule.last_status or '—' }}</span></td>
            <td>
              <div class="mailing-actions">
                <a class="btn btn-soft" href="{{ url_for('mailing_edit', rule_id=rule.id) }}">Изменить</a>
                <form method="post" action="{{ url_for('mailing_toggle', rule_id=rule.id) }}" style="display:inline;">
                  <button class="btn btn-secondary" type="submit">{{ 'Отключить' if rule.enabled else 'Включить' }}</button>
                </form>
                <form method="post" action="{{ url_for('mailing_send_now', rule_id=rule.id) }}" style="display:inline;">
                  <button class="btn btn-primary" type="submit">Отправить сейчас</button>
                </form>
                <form method="post" action="{{ url_for('mailing_delete', rule_id=rule.id) }}" style="display:inline;" onsubmit="return confirm('Удалить правило рассылки?');">
                  <button class="btn btn-secondary" type="submit">Удалить</button>
                </form>
              </div>
            </td>
          </tr>
          {% endfor %}
        {% else %}
          <tr><td colspan="8" class="empty">Правила авторассылки ещё не созданы.</td></tr>
        {% endif %}
      </tbody>
    </table>
  </div>
</section>
"""

MAILING_FORM_BODY = """
<div class="main-tabs">
  <a class="main-tab" href="{{ url_for('index', tab='approach') }}">Подход вагонов</a>
  <a class="main-tab" href="{{ url_for('index', tab='departure') }}">Отправление вагонов</a>
  <a class="main-tab" href="{{ url_for('index', tab='loading') }}">Погрузка</a>
  <a class="main-tab" href="{{ url_for('index', tab='station_idle') }}">Простои</a>
  <a class="main-tab" href="{{ url_for('index', tab='manual_filter') }}">Ручной фильтр</a>
  <a class="main-tab" href="{{ url_for('archive_search') }}">Архив</a>
  <a class="main-tab is-active" href="{{ url_for('mailing_rules') }}">Авторассылка справок</a>
</div>

<div class="breadcrumb">
  <a href="{{ url_for('mailing_rules') }}">Авторассылка справок</a>
  <span>•</span>
  <span>{{ page_title }}</span>
</div>

{% if error_message %}<div class="error">{{ error_message }}</div>{% endif %}
{% if success_message %}<div class="success">{{ success_message }}</div>{% endif %}

<section class="card" style="padding:14px;">
  <form method="post" class="activation-form">
    <div class="form-row">
      <div style="flex:1 1 320px; min-width:280px;">
        <div class="search-caption">Название рассылки</div>
        <input class="input" style="width:100%;" type="text" name="name" value="{{ rule.name }}" required>
      </div>
      <div style="flex:1 1 260px; min-width:240px;">
        <div class="search-caption">Тип справки</div>
        <select class="input" style="width:100%;" name="report_type" required>
          {% for item in report_options %}
            <option value="{{ item.value }}" {% if rule.report_type == item.value %}selected{% endif %}>{{ item.label }}</option>
          {% endfor %}
        </select>
      </div>
      <div style="min-width:180px;">
        <div class="search-caption">Активна</div>
        <label class="file-label" style="border-style:solid;">
          <input type="checkbox" name="enabled" {% if rule.enabled %}checked{% endif %}>
          <span>Включить правило</span>
        </label>
      </div>
    </div>

    <div class="form-row">
      <div style="flex:1 1 320px; min-width:280px;">
        <div class="search-caption">Получатели</div>
        <textarea class="search-input" style="height:88px; padding:8px 10px;" name="to" required>{{ rule.to }}</textarea>
      </div>
      <div style="flex:1 1 320px; min-width:280px;">
        <div class="search-caption">Копия</div>
        <textarea class="search-input" style="height:88px; padding:8px 10px;" name="cc">{{ rule.cc }}</textarea>
      </div>
      <div style="flex:1 1 320px; min-width:280px;">
        <div class="search-caption">Скрытая копия</div>
        <textarea class="search-input" style="height:88px; padding:8px 10px;" name="bcc">{{ rule.bcc }}</textarea>
      </div>
    </div>

    <div class="form-row">
      <div style="flex:1 1 360px; min-width:280px;">
        <div class="search-caption">Тема письма</div>
        <input class="input" style="width:100%;" type="text" name="subject" value="{{ rule.subject }}">
      </div>
      <div style="flex:1 1 260px; min-width:240px;">
        <div class="search-caption">Имя файла вложения</div>
        <input class="input" style="width:100%;" type="text" name="attach_filename_template" value="{{ rule.attach_filename_template }}">
      </div>
      <div style="min-width:240px;">
        <div class="search-caption">Добавлять дату/время в тему</div>
        <label class="file-label choice-label {% if rule.add_datetime_to_subject %}is-checked{% endif %}" style="border-style:solid;">
          <input type="checkbox" name="add_datetime_to_subject" {% if rule.add_datetime_to_subject %}checked{% endif %}>
          <span>Да</span>
        </label>
      </div>
    </div>

    <div>
      <div class="search-caption">Текст письма</div>
      <textarea class="search-input" style="height:130px; padding:8px 10px; width:100%;" name="body">{{ rule.body }}</textarea>
    </div>

    <div class="form-row">
      <div style="flex:1 1 280px; min-width:240px;">
        <div class="search-caption">Периодичность</div>
        <select class="input" style="width:100%;" name="schedule_type">
          {% for item in schedule_options %}
            <option value="{{ item.value }}" {% if rule.schedule_type == item.value %}selected{% endif %}>{{ item.label }}</option>
          {% endfor %}
        </select>
      </div>
      <div style="flex:1 1 280px; min-width:240px;">
        <div class="search-caption">Время отправки</div>
        <input class="input" style="width:100%;" type="text" name="times" value="{{ times_text }}" placeholder="08:00 или 08:00, 14:00">
      </div>
    </div>

    <div>
      <div class="search-caption">Дни недели (для режима «по выбранным дням недели»)</div>
      <div class="selection-tools">
        {% for item in weekday_options %}
        <label class="file-label choice-label {% if item.value in selected_weekdays %}is-checked{% endif %}" style="border-style:solid;">
          <input type="checkbox" name="weekdays" value="{{ item.value }}" {% if item.value in selected_weekdays %}checked{% endif %}>
          <span>{{ item.label }}</span>
        </label>
        {% endfor %}
      </div>
    </div>

    <div class="selection-tools">
      <button class="btn btn-primary" type="submit">Сохранить</button>
      <a class="btn btn-secondary" href="{{ url_for('mailing_rules') }}">Отмена</a>
    </div>

    <div class="mini-note">Поддерживаемые шаблоны имени файла: <span class="mono">{report_label}</span>, <span class="mono">{date}</span>, <span class="mono">{datetime}</span>.</div>
  </form>

<script>
(function(){
  document.querySelectorAll('.choice-label input[type="checkbox"]').forEach(function(input){
    function syncChoice(){
      const label = input.closest('.choice-label');
      if (label) label.classList.toggle('is-checked', !!input.checked);
    }
    input.addEventListener('change', syncChoice);
    syncChoice();
  });
})();
</script>
</section>
"""

MAILING_LOGS_BODY = """
<div class="main-tabs">
  <a class="main-tab" href="{{ url_for('index', tab='approach') }}">Подход вагонов</a>
  <a class="main-tab" href="{{ url_for('index', tab='departure') }}">Отправление вагонов</a>
  <a class="main-tab" href="{{ url_for('index', tab='loading') }}">Погрузка</a>
  <a class="main-tab" href="{{ url_for('index', tab='station_idle') }}">Простои</a>
  <a class="main-tab" href="{{ url_for('index', tab='manual_filter') }}">Ручной фильтр</a>
  <a class="main-tab" href="{{ url_for('archive_search') }}">Архив</a>
  <a class="main-tab is-active" href="{{ url_for('mailing_rules') }}">Авторассылка справок</a>
</div>

<div class="breadcrumb">
  <a href="{{ url_for('mailing_rules') }}">Авторассылка справок</a>
  <span>•</span>
  <span>Журнал</span>
</div>

{% if error_message %}<div class="error">{{ error_message }}</div>{% endif %}
{% if success_message %}<div class="success">{{ success_message }}</div>{% endif %}

<section class="card table-card">
  <div class="toolbar">
    <div>
      <div class="toolbar-title">Журнал авторассылки</div>
      <div class="toolbar-sub">Последние попытки отправки через Outlook</div>
    </div>
  </div>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>Дата начала</th>
          <th>Дата завершения</th>
          <th>Правило</th>
          <th>Справка</th>
          <th>Получатели</th>
          <th>Статус</th>
          <th>Сообщение</th>
          <th>Вложение</th>
        </tr>
      </thead>
      <tbody>
        {% if logs %}
          {% for entry in logs %}
          <tr>
            <td>{{ entry.started_at or '—' }}</td>
            <td>{{ entry.finished_at or '—' }}</td>
            <td>{{ entry.rule_name or '—' }}</td>
            <td>{{ report_labels.get(entry.report_type, entry.report_type) }}</td>
            <td>{{ entry.to or '—' }}</td>
            <td>{{ entry.status or '—' }}</td>
            <td>{{ entry.message or '—' }}</td>
            <td>{{ entry.attachment_name or '—' }}</td>
          </tr>
          {% endfor %}
        {% else %}
          <tr><td colspan="8" class="empty">Записей журнала пока нет.</td></tr>
        {% endif %}
      </tbody>
    </table>
  </div>
</section>
"""


MAP_BODY = """
<div class="main-tabs">
  <a class="main-tab {% if current_tab == 'approach' %}is-active{% endif %}" href="{{ url_for('index', tab='approach', archive_date=archive_date) }}">Подход вагонов</a>
  <a class="main-tab {% if current_tab == 'departure' %}is-active{% endif %}" href="{{ url_for('index', tab='departure', archive_date=archive_date) }}">Отправление вагонов</a>
  <a class="main-tab {% if current_tab == 'loading' %}is-active{% endif %}" href="{{ url_for('index', tab='loading', archive_date=archive_date) }}">Погрузка</a>
  <a class="main-tab {% if current_tab == 'station_idle' %}is-active{% endif %}" href="{{ url_for('index', tab='station_idle', archive_date=archive_date, idle_view=idle_view if current_tab == 'station_idle' else None) }}">Простои</a>
  <a class="main-tab {% if current_tab == 'raw_material' %}is-active{% endif %}" href="{{ url_for('index', tab='raw_material', archive_date=archive_date) }}">Сырье</a>
  <a class="main-tab {% if current_tab == 'technical_state' %}is-active{% endif %}" href="{{ url_for('technical_state_index') }}">Техническое состояние</a>
  <a class="main-tab {% if current_tab == 'manual_filter' %}is-active{% endif %}" href="{{ url_for('index', tab='manual_filter', archive_date=archive_date) }}">Ручной фильтр</a>
  <a class="main-tab {% if current_tab == 'archive' %}is-active{% endif %}" href="{{ url_for('archive_search') }}">Архив</a>
  <a class="main-tab {% if current_tab == 'mailing' %}is-active{% endif %}" href="{{ url_for('mailing_rules') }}">Авторассылка справок</a>
</div>

{% if current_tab == 'station_idle' %}
<div class="sub-tabs">
  <a class="sub-tab {% if idle_view == 'ugleuralskaya' %}is-active{% endif %}" href="{{ url_for('index', tab='station_idle', idle_view='ugleuralskaya', archive_date=archive_date) }}">Простой на станции {{ selected_station or destination_keyword or "Углеуральская" }}</a>
  <a class="sub-tab {% if idle_view == 'destination' %}is-active{% endif %}" href="{{ url_for('index', tab='station_idle', idle_view='destination', archive_date=archive_date) }}">Простой на станции назначения</a>
</div>
{% endif %}

{% if current_tab == 'loading' %}
<div class="sub-tabs">
  <a class="sub-tab {% if loading_mode == 'today' %}is-active{% endif %}" href="{{ url_for('index', tab='loading', loading_view='today', archive_date=archive_date) }}">Погрузка сегодня</a>
  <a class="sub-tab {% if loading_mode == 'yesterday' %}is-active{% endif %}" href="{{ url_for('index', tab='loading', loading_view='yesterday', archive_date=archive_date) }}">Погрузка вчера</a>
  <a class="sub-tab {% if loading_mode == 'pending' %}is-active{% endif %}" href="{{ url_for('index', tab='loading', loading_view='pending', archive_date=archive_date) }}">Погружены, но не отправлены более суток</a>
</div>
{% endif %}

<style>
  .map-page-card { overflow:hidden; }
  .map-toolbar { display:flex; align-items:center; justify-content:space-between; gap:10px; padding:10px 12px; border-bottom:1px solid var(--line-soft); background:var(--panel-soft); }
  .map-toolbar-left { min-width:0; }
  .map-toolbar-title { font-size:15px; font-weight:800; letter-spacing:-.02em; }
  .map-layout { min-height: calc(100vh - 250px); }
  .map-canvas-wrap { position:relative; min-height: 720px; background:#eef3f8; }
  .map-canvas { width:100%; height:100%; min-height: 720px; }
  .map-marker { width:42px; height:42px; border-radius:999px; border:2px solid #fff; background:var(--accent); color:#fff; display:flex; align-items:center; justify-content:center; font-size:14px; font-weight:800; box-shadow:0 8px 18px rgba(20,37,63,.18); cursor:pointer; user-select:none; }
  .map-status { position:absolute; left:12px; top:12px; z-index:20; max-width:520px; padding:12px; border-radius:12px; border:1px solid var(--line); background:#fff; color:var(--accent); font-size:12px; line-height:1.45; box-shadow:0 10px 28px rgba(20, 37, 63, .06); }
  .map-status.is-warn { background:#fff8ef; border-color:#f1ddba; color:#9a6418; }
  .map-status.is-error { background:#fff3f3; border-color:#efcaca; color:#a33636; }
</style>

<section class="card topbar">
  <div class="topbar-left">
    <div class="title">{{ app_title }} — Карта вагонов</div>
    <div class="meta">{{ current_tab_label }}{% if filter_caption %} • {{ filter_caption }}{% endif %}{% if archive_date %} • Архив: {{ archive_date }}{% endif %}</div>
  </div>
  <div class="topbar-right">
    <a class="btn btn-secondary" href="{{ back_url }}" data-no-loading="1">Назад</a>
  </div>
</section>

{% if success_message %}<div class="success card">{{ success_message }}</div>{% endif %}
{% if error_message %}<div class="error card">{{ error_message }}</div>{% endif %}

<section class="card map-page-card">
  <div class="map-toolbar">
    <div class="map-toolbar-left">
      <div class="map-toolbar-title">Карта России</div>
    </div>
    <div class="toolbar-right">
      <a class="btn btn-soft" href="{{ export_link }}">Excel детализация</a>
      <a class="btn btn-ghost" href="{{ raw_export_link }}">Excel исходные данные</a>
    </div>
  </div>

  <div class="map-layout">
    <div class="map-canvas-wrap">
      {% if not station_directory_available %}
      <div class="map-status is-error">Не найден локальный справочник станций: <span class="mono">{{ station_directory_path }}</span>. Положите файл справочника в папку <span class="mono">%APPDATA%\\ASU_PODHOD</span>.</div>
      {% elif not map_points %}
      <div class="map-status is-warn">Для выбранной выборки не найдено точек на карте. Проверьте, заполнена ли станция операции и есть ли она в локальном справочнике.</div>
      {% endif %}
      <div id="station-map-root" class="map-canvas"></div>
    </div>
  </div>
</section>

<script>
(function(){
  const points = {{ map_points_json|safe }};
  const mapRoot = document.getElementById('station-map-root');
  let map = null;

  function ensureStatus(message) {
    let status = document.querySelector('.map-status');
    if (!status) {
      status = document.createElement('div');
      status.className = 'map-status is-error';
      const wrap = document.querySelector('.map-canvas-wrap');
      if (wrap) {
        wrap.appendChild(status);
      }
    }
    status.classList.add('is-error');
    status.textContent = message;
  }

  function loadLeafletCss() {
    return new Promise((resolve, reject) => {
      const existing = document.querySelector('link[data-leaflet-css="1"]');
      if (existing) {
        resolve();
        return;
      }
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
      link.setAttribute('data-leaflet-css', '1');
      link.onload = () => resolve();
      link.onerror = () => reject(new Error('Не удалось загрузить стили Leaflet.'));
      document.head.appendChild(link);
    });
  }

  function loadLeafletScript() {
    return new Promise((resolve, reject) => {
      if (window.L) {
        resolve();
        return;
      }
      const existing = document.querySelector('script[data-leaflet-js="1"]');
      if (existing) {
        existing.addEventListener('load', () => resolve(), {once:true});
        existing.addEventListener('error', () => reject(new Error('Не удалось загрузить библиотеку карты.')), {once:true});
        return;
      }
      const script = document.createElement('script');
      script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
      script.async = true;
      script.defer = true;
      script.setAttribute('data-leaflet-js', '1');
      script.onload = () => resolve();
      script.onerror = () => reject(new Error('Не удалось загрузить библиотеку карты.'));
      document.head.appendChild(script);
    });
  }

  function escapeHtml(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function createMarker(point) {
    const icon = L.divIcon({
      className: 'map-marker-icon',
      html: `<div class="map-marker" title="${escapeHtml(point.station_name)}: ${point.count}">${point.count}</div>`,
      iconSize: [42, 42],
      iconAnchor: [21, 21],
    });
    return L.marker([point.latitude, point.longitude], { icon });
  }

  async function initMap() {
    if (!mapRoot) {
      return;
    }

    await loadLeafletCss();
    await loadLeafletScript();

    map = L.map(mapRoot, {
      zoomControl: true,
      preferCanvas: true,
    });

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap contributors'
    }).addTo(map);

    if (points.length) {
      const bounds = [];
      points.forEach((point) => {
        createMarker(point).addTo(map);
        bounds.push([point.latitude, point.longitude]);
      });
      if (bounds.length === 1) {
        map.setView(bounds[0], 7);
      } else {
        map.fitBounds(bounds, { padding: [30, 30] });
      }
    } else {
      map.setView([61.524, 105.3188], 3);
    }

    window.setTimeout(() => map.invalidateSize(), 100);
    window.addEventListener('resize', () => {
      if (map) {
        map.invalidateSize();
      }
    });
  }

  initMap().catch((error) => {
    console.error(error);
    ensureStatus(error && error.message ? error.message : 'Не удалось загрузить карту.');
  });

  window.addEventListener('pageshow', function(event) {
    if (event.persisted && map) {
      window.setTimeout(() => map.invalidateSize(), 0);
    }
  });
})();
</script>
"""
