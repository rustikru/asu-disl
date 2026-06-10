CLAIMS_UGLEURALSKAYA_BODY = r'''
<div class="main-tabs">
  <a class="main-tab {% if current_tab == 'approach' %}is-active{% endif %}" href="{{ url_for('index', tab='approach') }}">Подход вагонов</a>
  <a class="main-tab {% if current_tab == 'departure' %}is-active{% endif %}" href="{{ url_for('index', tab='departure') }}">Отправление вагонов</a>
  <a class="main-tab {% if current_tab == 'loading' %}is-active{% endif %}" href="{{ url_for('index', tab='loading') }}">Погрузка</a>
  <a class="main-tab is-active" href="{{ url_for('index', tab='station_idle') }}">Простои</a>
  <a class="main-tab {% if current_tab == 'raw_material' %}is-active{% endif %}" href="{{ url_for('index', tab='raw_material') }}">Сырье</a>
  <a class="main-tab {% if current_tab == 'technical_state' %}is-active{% endif %}" href="{{ url_for('technical_state_index') }}">Техническое состояние</a>
  <a class="main-tab {% if current_tab == 'manual_filter' %}is-active{% endif %}" href="{{ url_for('index', tab='manual_filter') }}">Ручной фильтр</a>
  <a class="main-tab {% if current_tab == 'archive' %}is-active{% endif %}" href="{{ url_for('archive_search') }}">Архив</a>
  <a class="main-tab {% if current_tab == 'mailing' %}is-active{% endif %}" href="{{ url_for('mailing_rules') }}">Авторассылка справок</a>
</div>

<div class="sub-tabs">
  <a class="sub-tab" href="{{ url_for('index', tab='station_idle', idle_view='ugleuralskaya') }}">Простой на станции {{ selected_work_station or selected_station or "Углеуральская" }}</a>
  <a class="sub-tab" href="{{ url_for('index', tab='station_idle', idle_view='destination') }}">Простой на станции назначения</a>
  <a class="sub-tab is-active" href="{{ url_for('claims_ugleuralskaya_index') }}">Претензии на {{ selected_work_station or selected_station or "Углеуральской" }}</a>
</div>

<style>
.claims-row-zero td{background:#f5f6f8;color:#6e7b8b;}
.claims-row-penalty td{background:#fff4f2;color:#8d2b2b;}
.claims-row-high td{background:#f3cbc6;color:#7d312a;}
.claims-row-high td .mono{color:#7d312a;}
.claims-summary-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin-bottom:12px;}
.claims-chart{padding:12px;display:grid;gap:10px;}
.claims-chart-row{display:grid;grid-template-columns:180px 1fr auto;gap:10px;align-items:center;}
.claims-chart-label{font-size:13px;color:#5c6d80;}
.claims-chart-bar-wrap{height:12px;background:#eef2f6;border-radius:999px;overflow:hidden;}
.claims-chart-bar{height:100%;border-radius:999px;background:linear-gradient(90deg,#cc4b4b,#e59898);}
.claims-chart-value{font-weight:700;font-size:13px;white-space:nowrap;}
.claims-small-btn{padding:6px 8px;border-radius:9px;min-width:68px;height:34px;display:inline-flex;align-items:center;justify-content:center;white-space:nowrap;}
.claims-comment-form{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:6px;align-items:center;}
.claims-status-chip{display:inline-flex;align-items:center;padding:3px 8px;border-radius:999px;font-size:12px;font-weight:700;background:#eef3f8;color:#46627c;}
.claims-status-chip.departed{background:#f7e9e9;color:#8d2b2b;}
.claims-links{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end;}
.claims-detail-table{table-layout:fixed !important; min-width:2420px !important; font-size:12px;}
.claims-detail-table th,.claims-detail-table td{padding:6px 8px; line-height:1.2; vertical-align:top; white-space:normal;}
.claims-detail-table thead th{font-size:11px;}
.claims-detail-table .col-wagon{width:108px; min-width:108px;}
.claims-detail-table .col-status{width:112px; min-width:112px;}
.claims-detail-table .col-station{width:145px; min-width:145px;}
.claims-detail-table .col-kind{width:210px; min-width:210px;}
.claims-detail-table .col-shipper{width:220px; min-width:220px;}
.claims-detail-table .col-cargo{width:250px; min-width:250px;}
.claims-detail-table .col-prev-cargo{width:250px; min-width:250px;}
.claims-detail-table .col-owner{width:145px; min-width:145px;}
.claims-detail-table .col-date{width:118px; min-width:118px;}
.claims-detail-table .col-num{width:78px; min-width:78px; text-align:center;}
.claims-detail-table .col-comment{width:210px; min-width:210px;}
.claims-detail-wrap{display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; line-height:1.2; max-height:2.4em; word-break:break-word;}
.claims-detail-table .num{text-align:center; white-space:nowrap;}
.detail-table tbody tr.asu-selected-row td{background:#fff6bf !important; box-shadow: inset 0 1px 0 #ead36c, inset 0 -1px 0 #ead36c;}
.claims-norms-shell{max-width:1180px; margin:0 auto; display:grid; gap:12px;}
.claims-norms-kind-table{width:100%; table-layout:fixed;}
.claims-norms-kind-table th:nth-child(1), .claims-norms-kind-table td:nth-child(1){width:58%;}
.claims-norms-kind-table th:nth-child(2), .claims-norms-kind-table td:nth-child(2), .claims-norms-kind-table th:nth-child(3), .claims-norms-kind-table td:nth-child(3){width:21%;}
.claims-norms-kind-table .search-input{max-width:120px; margin-left:auto;}
.claims-norms-shipper-form{display:grid; grid-template-columns:minmax(280px,1.7fr) 150px 150px auto; gap:10px; align-items:end;}
.claims-norms-shipper-table{width:100%; table-layout:fixed;}
.claims-norms-shipper-table th:nth-child(2), .claims-norms-shipper-table td:nth-child(2), .claims-norms-shipper-table th:nth-child(3), .claims-norms-shipper-table td:nth-child(3){width:120px;}
.claims-norms-shipper-table th:nth-child(4), .claims-norms-shipper-table td:nth-child(4){width:130px;}
.claims-filter-form{display:grid; grid-template-columns:minmax(165px,1fr) minmax(130px,.82fr) minmax(155px,.95fr) minmax(130px,.78fr) minmax(145px,.88fr) minmax(145px,.88fr) minmax(140px,.8fr) minmax(140px,.8fr) auto; gap:10px; align-items:end;}
.claims-filter-actions{display:flex; gap:8px; flex-wrap:nowrap; align-items:end; justify-content:flex-start;}
</style>

<section class="card topbar">
  <div class="topbar-left">
    <div class="title">{{ app_title }} — Претензии на {{ selected_work_station or selected_station or "Углеуральской" }}</div>
    <div class="meta">{{ source_meta }}{% if archive_date %} • Архив претензий: {{ archive_date }}{% endif %}</div>
  </div>
  <div class="topbar-right" style="display:flex; gap:8px; align-items:center; flex-wrap:wrap; justify-content:flex-end;">
    <form class="archive-form" method="get" action="{{ url_for('claims_ugleuralskaya_index') }}">
      <input class="archive-date" type="date" name="archive_date" value="{{ archive_date or '' }}">
      <button class="btn btn-soft" type="submit">Открыть дату</button>
      {% if archive_date %}<a class="btn btn-secondary" href="{{ url_for('claims_ugleuralskaya_index') }}">Текущая</a>{% endif %}
    </form>
    <div class="claims-links">
      <a class="btn btn-secondary" href="{{ url_for('claims_ugleuralskaya_norms') }}">Нормативы</a>
      <a class="btn btn-soft" href="{{ url_for('claims_ugleuralskaya_reasons') }}">Комментарии</a>
      <a class="btn btn-soft" href="{{ url_for('claims_ugleuralskaya_export', archive_date=archive_date if archive_date else None, station=selected_station if selected_station else None, kind_group=selected_kind_group if selected_kind_group else None, shipper=selected_shipper if selected_shipper else None, cargo_name=selected_cargo_name if selected_cargo_name else None, previous_cargo=selected_previous_cargo if selected_previous_cargo else None, period_from=selected_period_from if selected_period_from else None, period_to=selected_period_to if selected_period_to else None, status=selected_status if selected_status else None, comment=selected_comment if selected_comment else None) }}">Скачать Excel</a>
      <a class="btn btn-secondary" href="{{ url_for('claims_ugleuralskaya_index') }}">Обновить</a>
    </div>
  </div>
</section>

{% if success_message %}<div class="success card">{{ success_message }}</div>{% endif %}
{% if error_message %}<div class="error card">{{ error_message }}</div>{% endif %}

<section class="card" style="padding:12px; margin-bottom:12px; display:grid; gap:12px;">
  <form class="claims-filter-form" method="get" action="{{ url_for('claims_ugleuralskaya_index') }}">
    {% if archive_date %}<input type="hidden" name="archive_date" value="{{ archive_date }}">{% endif %}
    <label style="display:grid; gap:6px;">
      <span class="toolbar-sub">Станция</span>
      <select class="search-input" name="station">
        <option value="">Все станции</option>
        {% for option in station_options %}
        <option value="{{ option }}" {% if option == selected_station %}selected{% endif %}>{{ option }}</option>
        {% endfor %}
      </select>
    </label>
    <label style="display:grid; gap:6px;">
      <span class="toolbar-sub">Род вагона</span>
      <select class="search-input" name="kind_group">
        <option value="">Все</option>
        {% for option in kind_options %}
        <option value="{{ option.value }}" {% if option.value == selected_kind_group %}selected{% endif %}>{{ option.label }}</option>
        {% endfor %}
      </select>
    </label>
    <label style="display:grid; gap:6px;">
      <span class="toolbar-sub">Грузоотправитель</span>
      <select class="search-input" name="shipper">
        <option value="">Все</option>
        {% for option in shipper_options %}
        <option value="{{ option }}" {% if option == selected_shipper %}selected{% endif %}>{{ option }}</option>
        {% endfor %}
      </select>
    </label>
    <label style="display:grid; gap:6px;">
      <span class="toolbar-sub">Статус</span>
      <select class="search-input" name="status">
        <option value="">Все</option>
        <option value="active" {% if selected_status == 'active' %}selected{% endif %}>На ПНП</option>
        <option value="departed" {% if selected_status == 'departed' %}selected{% endif %}>Уехал</option>
      </select>
    </label>
    <label style="display:grid; gap:6px;">
      <span class="toolbar-sub">Груз</span>
      <select class="search-input" name="cargo_name">
        <option value="">Все</option>
        {% for option in cargo_name_options %}
        <option value="{{ option }}" {% if option == selected_cargo_name %}selected{% endif %}>{{ option }}</option>
        {% endfor %}
      </select>
    </label>
    <label style="display:grid; gap:6px;">
      <span class="toolbar-sub">Ранее выгруженный груз</span>
      <select class="search-input" name="previous_cargo">
        <option value="">Все</option>
        {% for option in previous_cargo_options %}
        <option value="{{ option }}" {% if option == selected_previous_cargo %}selected{% endif %}>{{ option }}</option>
        {% endfor %}
      </select>
    </label>
    <label style="display:grid; gap:6px;">
      <span class="toolbar-sub">Комментарий</span>
      <select class="search-input" name="comment">
        <option value="">Все</option>
        {% for option in comment_options %}
        <option value="{{ option }}" {% if option == selected_comment %}selected{% endif %}>{{ option }}</option>
        {% endfor %}
      </select>
    </label>
    <label style="display:grid; gap:6px;">
      <span class="toolbar-sub">Период расчёта: от</span>
      <input class="search-input" type="date" name="period_from" value="{{ selected_period_from or '' }}">
    </label>
    <label style="display:grid; gap:6px;">
      <span class="toolbar-sub">Период расчёта: до</span>
      <input class="search-input" type="date" name="period_to" value="{{ selected_period_to or '' }}">
    </label>
    <div class="claims-filter-actions">
      <button class="btn btn-primary" type="submit">Применить</button>
      <a class="btn btn-secondary" href="{{ url_for('claims_ugleuralskaya_index', archive_date=archive_date if archive_date else None) }}">Сбросить</a>
    </div>
  </form>
</section>

<div class="header-grid">
  <section class="card metric metric-danger">
    <div class="label">Всего штраф</div>
    <div class="value">{{ total_amount_label }}</div>
    <div class="sub">Вагоны: {{ total_count }}</div>
  </section>
  <section class="card metric">
    <div class="label">Количество со штрафом</div>
    <div class="value">{{ penalty_count }}</div>
    <div class="sub">Без штрафа: {{ zero_penalty_count }}</div>
  </section>
  <section class="card metric">
    <div class="label">Всего вагонов</div>
    <div class="value">{{ total_count }}</div>
    <div class="sub">По текущему фильтру</div>
  </section>

</div>

<div class="claims-summary-grid">
  <section class="card claims-chart">
    <div>
      <div class="toolbar-title">Диаграмма: сумма штрафа</div>
      <div class="toolbar-sub">По группам рода вагона</div>
    </div>
    {% for item in amount_chart_rows %}
    <div class="claims-chart-row">
      <div class="claims-chart-label">{{ item.label }}</div>
      <div class="claims-chart-bar-wrap"><div class="claims-chart-bar" style="width: {{ item.width }}%;"></div></div>
      <div class="claims-chart-value">{{ item.value_label }}</div>
    </div>
    {% endfor %}
  </section>
  <section class="card claims-chart">
    <div>
      <div class="toolbar-title">Диаграмма: простой, сут.</div>
      <div class="toolbar-sub">Средняя длительность по роду вагона</div>
    </div>
    {% for item in days_chart_rows %}
    <div class="claims-chart-row">
      <div class="claims-chart-label">{{ item.label }}</div>
      <div class="claims-chart-bar-wrap"><div class="claims-chart-bar" style="width: {{ item.width }}%;"></div></div>
      <div class="claims-chart-value">{{ item.value_label }}</div>
    </div>
    {% endfor %}
  </section>
</div>

<section class="card table-card" style="margin-bottom:12px;">
  <div class="toolbar">
    <div>
      <div class="toolbar-title">Сводка по роду вагона</div>
      <div class="toolbar-sub">Количество вагонов, вагонов со штрафом и сумма претензий</div>
    </div>
  </div>
  <div class="table-wrap" style="max-height:none;">
    <table class="summary-table">
      <thead>
        <tr>
          <th class="c-name">Род вагона</th>
          <th class="num-col">Вагонов</th>
          <th class="num-col">Со штрафом</th>
          <th class="num-col" style="min-width:140px;">Сумма штрафа</th>
        </tr>
      </thead>
      <tbody>
        {% for item in summary_rows %}
        <tr class="{{ item.row_class }}">
          <td class="c-name">{% if item.link %}<a class="summary-row-link" href="{{ item.link }}">{{ item.label }}</a>{% else %}<span class="summary-row-label">{{ item.label }}</span>{% endif %}</td>
          <td class="num">{{ item.count }}</td>
          <td class="num">{{ item.penalty_count }}</td>
          <td class="num">{{ item.amount_label }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</section>

<section class="card table-card">
  <div class="toolbar">
    <div>
      <div class="toolbar-title">Детализация</div>
      <div class="toolbar-sub">Расчёт: простой − бесплатно = платный простой; исключения не штрафуются</div>
    </div>
    <div class="toolbar-right">
      <span class="badge" id="claims-visible-count-badge">Показано: {{ total_count }}</span>
      <button class="btn btn-ghost" type="button" id="clear-claims-filters">Сбросить фильтры</button>
    </div>
  </div>
  {% if records %}
  <div class="table-wrap">
    <table class="detail-table claims-detail-table" id="claims-detail-table">
      <thead>
        <tr>
          <th class="col-wagon" data-col-index="0"><div class="th-wrap"><span>Вагон</span><button type="button" class="col-filter-btn" data-col-index="0">▾</button></div></th>
          <th class="col-status" data-col-index="1"><div class="th-wrap"><span>Статус</span><button type="button" class="col-filter-btn" data-col-index="1">▾</button></div></th>
          <th class="col-station" data-col-index="2"><div class="th-wrap"><span>Станция</span><button type="button" class="col-filter-btn" data-col-index="2">▾</button></div></th>
          <th class="col-kind" data-col-index="3"><div class="th-wrap"><span>Род вагона</span><button type="button" class="col-filter-btn" data-col-index="3">▾</button></div></th>
          <th class="col-shipper" data-col-index="4"><div class="th-wrap"><span>Грузоотправитель</span><button type="button" class="col-filter-btn" data-col-index="4">▾</button></div></th>
          <th class="col-cargo" data-col-index="5"><div class="th-wrap"><span>Груз</span><button type="button" class="col-filter-btn" data-col-index="5">▾</button></div></th>
          <th class="col-prev-cargo" data-col-index="6"><div class="th-wrap"><span>Ранее выгруженный груз</span><button type="button" class="col-filter-btn" data-col-index="6">▾</button></div></th>
          <th class="col-owner" data-col-index="7"><div class="th-wrap"><span>Собственник</span><button type="button" class="col-filter-btn" data-col-index="7">▾</button></div></th>
          <th class="col-date" data-col-index="8"><div class="th-wrap"><span>Прибыл</span><button type="button" class="col-filter-btn" data-col-index="8">▾</button></div></th>
          <th class="col-date" data-col-index="9"><div class="th-wrap"><span>Уехал</span><button type="button" class="col-filter-btn" data-col-index="9">▾</button></div></th>
          <th class="col-date" data-col-index="10"><div class="th-wrap"><span>Дата факт</span><button type="button" class="col-filter-btn" data-col-index="10">▾</button></div></th>
          <th class="col-num" data-col-index="11"><div class="th-wrap"><span>Простой</span><button type="button" class="col-filter-btn" data-col-index="11">▾</button></div></th>
          <th class="col-num" data-col-index="12"><div class="th-wrap"><span>Бесплатно</span><button type="button" class="col-filter-btn" data-col-index="12">▾</button></div></th>
          <th class="col-num" data-col-index="13"><div class="th-wrap"><span>Платный</span><button type="button" class="col-filter-btn" data-col-index="13">▾</button></div></th>
          <th class="col-num" data-col-index="14"><div class="th-wrap"><span>Ставка</span><button type="button" class="col-filter-btn" data-col-index="14">▾</button></div></th>
          <th class="col-num" data-col-index="15"><div class="th-wrap"><span>Сумма</span><button type="button" class="col-filter-btn" data-col-index="15">▾</button></div></th>
          <th class="col-comment" data-col-index="16"><div class="th-wrap"><span>Комментарии</span><button type="button" class="col-filter-btn" data-col-index="16">▾</button></div></th>
        </tr>
      </thead>
      <tbody>
        {% for item in records %}
        <tr class="{{ item.row_class }}" data-detail-row="1">
          <td class="mono col-wagon">{{ item.wagon_number }}</td>
          <td class="col-status"><span class="claims-status-chip {% if item.status_code == 'departed' %}departed{% endif %}">{{ item.status_label }}</span></td>
          <td class="col-station"><div class="claims-detail-wrap">{{ item.station }}</div></td>
          <td class="col-kind"><div class="claims-detail-wrap">{{ item.kind_label }}</div></td>
          <td class="col-shipper"><div class="claims-detail-wrap">{{ item.shipper }}</div></td>
          <td class="col-cargo"><div class="claims-detail-wrap">{{ item.cargo_name }}</div></td>
          <td class="col-prev-cargo"><div class="claims-detail-wrap">{{ item.previous_cargo or '—' }}</div></td>
          <td class="col-owner"><div class="claims-detail-wrap">{{ item.owner }}</div></td>
          <td class="col-date">{{ item.arrived_at }}</td>
          <td class="col-date">{{ item.departed_at }}</td>
          <td class="col-date">{{ item.fact_at }}</td>
          <td class="num col-num">{{ item.total_days }}</td>
          <td class="num col-num">{{ item.free_days }}</td>
          <td class="num col-num">{{ item.payable_days }}</td>
          <td class="num col-num">{{ item.rate_label }}</td>
          <td class="num col-num">{{ item.amount_label }}</td>
          <td class="col-comment">
            <div class="claims-detail-wrap" style="margin-bottom:4px;">{{ item.comment_text or '—' }}</div>
            {% if not archive_date %}
            <form class="claims-comment-form" method="post" action="{{ url_for('claims_ugleuralskaya_comment_save') }}">
              <input type="hidden" name="wagon_number" value="{{ item.wagon_number }}">
              <input type="hidden" name="arrived_at_iso" value="{{ item.arrived_at_iso }}">
              <input type="hidden" name="cycle_id" value="{{ item.cycle_id or "" }}">
              <input type="hidden" name="next" value="{{ request.full_path if request.query_string else request.path }}">
              <input type="hidden" name="comment_effective_date" value="{{ item.period_date_key }}">
              <select class="search-input" name="comment_text">
                <option value="">—</option>
                {% for reason in comment_reasons %}
                <option value="{{ reason }}" {% if reason == item.comment_text %}selected{% endif %}>{{ reason }}</option>
                {% endfor %}
              </select>
              <button class="btn btn-soft claims-small-btn" type="submit">Сохр.</button>
            </form>
            {% endif %}
            {% if item.comment_updated_at %}<div class="toolbar-sub" style="margin-top:4px;">{{ item.comment_updated_at }}</div>{% endif %}
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% else %}
  <div class="empty">Нет данных для расчёта претензий по выбранным условиям.</div>
  {% endif %}
</section>

<script>
(function(){
  const table = document.getElementById('claims-detail-table');
  if (!table) return;
  const tbody = table.tBodies[0];
  const rows = Array.from(tbody.querySelectorAll('tr[data-detail-row="1"]'));
  const buttons = Array.from(table.querySelectorAll('.col-filter-btn'));
  const clearBtn = document.getElementById('clear-claims-filters');
  const visibleBadge = document.getElementById('claims-visible-count-badge');
  const activeFilters = new Map();
  let popover = null;
  let activeKey = null;
  let activeButton = null;

  function cellText(row, colIndex){
    const cell = row.cells[colIndex];
    if (!cell) return '';
    const select = cell.querySelector('select');
    if (select) return (select.value || '').trim();
    return ((cell.innerText || cell.textContent || '').replace(/\s+/g, ' ')).trim();
  }

  function rowMatches(row, excludeKey){
    for (const [key, allowed] of activeFilters.entries()) {
      if (excludeKey !== undefined && String(key) === String(excludeKey)) continue;
      if (!allowed) continue;
      if (allowed.size === 0) return false;
      if (!allowed.has(cellText(row, Number(key)))) return false;
    }
    return true;
  }

  function uniqueValues(colIndex){
    const values = new Set();
    const key = String(colIndex);
    rows.forEach((row) => {
      if (rowMatches(row, key)) values.add(cellText(row, colIndex));
    });
    return Array.from(values).sort((a, b) => a.localeCompare(b, 'ru', { numeric: true, sensitivity: 'base' }));
  }

  function updateButtons(){
    buttons.forEach((btn) => {
      const key = btn.dataset.colIndex;
      btn.classList.toggle('is-active', activeFilters.has(key));
    });
  }

  function applyFilters(){
    let visible = 0;
    rows.forEach((row) => {
      const show = rowMatches(row);
      row.style.display = show ? '' : 'none';
      if (show) visible += 1;
    });
    updateButtons();
    if (visibleBadge) visibleBadge.textContent = `Показано: ${visible}`;
  }

  function closePopover(){
    if (popover) popover.remove();
    popover = null;
    activeKey = null;
    activeButton = null;
  }

  function positionPopover(button, node){
    const rect = button.getBoundingClientRect();
    const margin = 12;
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const width = node.offsetWidth || 320;
    const height = node.offsetHeight || 320;
    let left = rect.right - width;
    left = Math.max(margin, Math.min(left, vw - width - margin));
    let top = rect.bottom + 8;
    if (top + height > vh - margin) top = rect.top - height - 8;
    if (top < margin) top = margin;
    node.style.left = `${left}px`;
    node.style.top = `${top}px`;
    node.style.maxHeight = `${Math.max(220, vh - margin * 2)}px`;
  }

  function renderOptions(optionsBox, values, current, key, query=''){
    const q = (query || '').trim().toLowerCase();
    optionsBox.innerHTML = '';
    const filtered = values.filter((value) => (value || '').toLowerCase().includes(q));
    if (!filtered.length){
      const empty = document.createElement('div');
      empty.className = 'filter-empty';
      empty.textContent = 'Нет значений';
      optionsBox.appendChild(empty);
      return;
    }
    filtered.forEach((value) => {
      const label = document.createElement('label');
      label.className = 'filter-item';
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.value = value;
      checkbox.checked = current.has(value);
      checkbox.addEventListener('change', () => {
        if (checkbox.checked) current.add(value);
        else current.delete(value);
        const allValues = uniqueValues(Number(key));
        if (current.size === allValues.length) activeFilters.delete(key);
        else activeFilters.set(key, new Set(current));
        applyFilters();
      });
      const text = document.createElement('span');
      text.textContent = value || 'Пусто';
      label.appendChild(checkbox);
      label.appendChild(text);
      optionsBox.appendChild(label);
    });
  }

  function openPopover(button){
    const key = String(button.dataset.colIndex);
    if (popover && activeKey === key){
      closePopover();
      return;
    }
    closePopover();
    activeKey = key;
    activeButton = button;

    const values = uniqueValues(Number(key));
    const current = activeFilters.has(key)
      ? new Set(Array.from(activeFilters.get(key) || []).filter((value) => values.includes(value)))
      : new Set(values);

    popover = document.createElement('div');
    popover.className = 'filter-popover';
    popover.innerHTML = `
      <div style="display:grid; gap:8px;">
        <input type="search" class="search-input" placeholder="Поиск">
        <div class="filter-actions">
          <button type="button" data-action="all">Выбрать все</button>
          <button type="button" data-action="none">Снять все</button>
          <button type="button" data-action="reset">Сбросить</button>
        </div>
        <div class="filter-list" style="max-height:220px; overflow:auto;"></div>
      </div>`;
    document.body.appendChild(popover);
    positionPopover(button, popover);

    const optionsBox = popover.querySelector('.filter-list');
    const search = popover.querySelector('input[type="search"]');
    renderOptions(optionsBox, values, current, key);

    search.addEventListener('input', () => renderOptions(optionsBox, values, current, key, search.value));
    popover.addEventListener('click', (event) => {
      const action = event.target?.dataset?.action;
      if (!action) return;
      if (action === 'all'){
        current.clear();
        values.forEach((value) => current.add(value));
        activeFilters.delete(key);
        applyFilters();
        renderOptions(optionsBox, values, current, key, search.value);
        return;
      }
      if (action === 'none'){
        current.clear();
        activeFilters.set(key, new Set());
        applyFilters();
        renderOptions(optionsBox, values, current, key, search.value);
        return;
      }
      if (action === 'reset'){
        activeFilters.delete(key);
        current.clear();
        values.forEach((value) => current.add(value));
        applyFilters();
        renderOptions(optionsBox, values, current, key, search.value);
      }
    });
  }

  buttons.forEach((button) => button.addEventListener('click', (event) => {
    event.preventDefault();
    event.stopPropagation();
    openPopover(button);
  }));

  if (clearBtn) clearBtn.addEventListener('click', () => {
    activeFilters.clear();
    applyFilters();
    closePopover();
  });

  document.addEventListener('click', (event) => {
    if (!popover) return;
    if (popover.contains(event.target)) return;
    if (event.target.closest('.col-filter-btn')) return;
    closePopover();
  });

  window.addEventListener('resize', () => {
    if (popover && activeButton) positionPopover(activeButton, popover);
  });

  rows.forEach((row) => {
    row.addEventListener('click', (event) => {
      const target = event.target;
      if (target && target.closest('a, button, input, select, textarea, label')) return;
      rows.forEach((item) => { if (item !== row) item.classList.remove('asu-selected-row'); });
      row.classList.toggle('asu-selected-row');
    });
  });

  applyFilters();
})();
</script>
'''

CLAIMS_UGLEURALSKAYA_NORMS_BODY = r'''
<div class="main-tabs">
  <a class="main-tab" href="{{ url_for('index', tab='approach') }}">Подход вагонов</a>
  <a class="main-tab" href="{{ url_for('index', tab='departure') }}">Отправление вагонов</a>
  <a class="main-tab" href="{{ url_for('index', tab='loading') }}">Погрузка</a>
  <a class="main-tab is-active" href="{{ url_for('index', tab='station_idle') }}">Простои</a>
</div>
<div class="sub-tabs">
  <a class="sub-tab" href="{{ url_for('claims_ugleuralskaya_index') }}">Претензии на {{ selected_work_station or selected_station or "Углеуральской" }}</a>
  <a class="sub-tab is-active" href="{{ url_for('claims_ugleuralskaya_norms') }}">Нормативы</a>
  <a class="sub-tab" href="{{ url_for('claims_ugleuralskaya_reasons') }}">Комментарии</a>
</div>
<style>
.claims-norms-shell{max-width:1180px; margin:0 auto; display:grid; gap:12px;}
.claims-norms-kind-table{width:100%; table-layout:fixed;}
.claims-norms-kind-table th:nth-child(1), .claims-norms-kind-table td:nth-child(1){width:58%;}
.claims-norms-kind-table th:nth-child(2), .claims-norms-kind-table td:nth-child(2), .claims-norms-kind-table th:nth-child(3), .claims-norms-kind-table td:nth-child(3){width:21%;}
.claims-norms-kind-table .search-input{max-width:120px; margin-left:auto;}
.claims-norms-shipper-form{display:grid; grid-template-columns:minmax(280px,1.7fr) 150px 150px auto; gap:10px; align-items:end;}
.claims-norms-shipper-table{width:100%; table-layout:fixed;}
.claims-norms-shipper-table th:nth-child(2), .claims-norms-shipper-table td:nth-child(2), .claims-norms-shipper-table th:nth-child(3), .claims-norms-shipper-table td:nth-child(3){width:120px;}
.claims-norms-shipper-table th:nth-child(4), .claims-norms-shipper-table td:nth-child(4){width:130px;}
.claims-filter-form{display:grid; grid-template-columns:minmax(165px,1fr) minmax(130px,.82fr) minmax(155px,.95fr) minmax(130px,.78fr) minmax(145px,.88fr) minmax(145px,.88fr) minmax(140px,.8fr) minmax(140px,.8fr) auto; gap:10px; align-items:end;}
.claims-filter-actions{display:flex; gap:8px; flex-wrap:nowrap; align-items:end; justify-content:flex-start;}
</style>
<section class="card topbar">
  <div class="topbar-left">
    <div class="title">Нормативы претензий</div>
    <div class="meta">Отдельные нормативы по роду вагона и по грузоотправителю</div>
  </div>
  <div class="topbar-right"><a class="btn btn-secondary" href="{{ url_for('claims_ugleuralskaya_index') }}">Назад</a></div>
</section>
{% if success_message %}<div class="success card">{{ success_message }}</div>{% endif %}
{% if error_message %}<div class="error card">{{ error_message }}</div>{% endif %}
<div class="claims-norms-shell">
<section class="card table-card" style="margin-bottom:12px;">
  <div class="toolbar"><div><div class="toolbar-title">Нормативы по роду вагона</div><div class="toolbar-sub">Для порожних вагонов и как резерв для гружёных</div></div></div>
  <form method="post" action="{{ url_for('claims_ugleuralskaya_norms_save_kinds') }}" style="padding:12px; display:grid; gap:12px;">
    <div class="table-wrap" style="max-height:none;">
      <table class="summary-table claims-norms-kind-table">
        <thead><tr><th>Группа</th><th class="num-col">Бесплатно, сут.</th><th class="num-col">Ставка, ₽/сут.</th></tr></thead>
        <tbody>
          {% for item in kind_rules %}
          <tr>
            <td>{{ item.label }}</td>
            <td><input class="search-input" type="number" min="0" name="free_days_{{ item.code }}" value="{{ item.free_days }}"></td>
            <td><input class="search-input" type="number" min="0" name="rate_{{ item.code }}" value="{{ item.rate }}"></td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
    <div><button class="btn btn-primary" type="submit">Сохранить нормативы по роду вагона</button></div>
  </form>
</section>
<section class="card table-card">
  <div class="toolbar"><div><div class="toolbar-title">Нормативы по грузоотправителю</div><div class="toolbar-sub">Используются для гружёных вагонов</div></div></div>
  <div style="padding:12px; display:grid; gap:12px;">
    <form method="post" action="{{ url_for('claims_ugleuralskaya_norms_upsert_shipper') }}" class="claims-norms-shipper-form">
      <label style="display:grid; gap:6px;"><span class="toolbar-sub">Грузоотправитель</span><input class="search-input" type="text" name="shipper_name" required></label>
      <label style="display:grid; gap:6px;"><span class="toolbar-sub">Бесплатно, сут.</span><input class="search-input" type="number" min="0" name="free_days" value="0"></label>
      <label style="display:grid; gap:6px;"><span class="toolbar-sub">Ставка, ₽/сут.</span><input class="search-input" type="number" min="0" name="rate" value="0"></label>
      <div><button class="btn btn-primary" type="submit">Сохранить</button></div>
    </form>
    <div class="table-wrap" style="max-height:none;">
      <table class="summary-table claims-norms-shipper-table">
        <thead><tr><th>Грузоотправитель</th><th class="num-col">Бесплатно</th><th class="num-col">Ставка</th><th class="num-col">Действие</th></tr></thead>
        <tbody>
          {% for item in shipper_rules %}
          <tr>
            <td>{{ item.name }}</td>
            <td class="num">{{ item.free_days }}</td>
            <td class="num">{{ item.rate_label }}</td>
            <td class="num">
              <form method="post" action="{{ url_for('claims_ugleuralskaya_norms_delete_shipper') }}" onsubmit="return confirm('Удалить норматив грузоотправителя?');">
                <input type="hidden" name="shipper_name" value="{{ item.name }}">
                <button class="btn btn-secondary" type="submit">Удалить</button>
              </form>
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  </div>
</section>
<section class="card table-card">
  <div class="toolbar"><div><div class="toolbar-title">Нормативы по грузу</div><div class="toolbar-sub">Используются для гружёных вагонов после грузоотправителя</div></div></div>
  <div style="padding:12px; display:grid; gap:12px;">
    <form method="post" action="{{ url_for('claims_ugleuralskaya_norms_upsert_cargo') }}" class="claims-norms-shipper-form">
      <label style="display:grid; gap:6px;"><span class="toolbar-sub">Груз</span><input class="search-input" type="text" name="cargo_name" required></label>
      <label style="display:grid; gap:6px;"><span class="toolbar-sub">Бесплатно, сут.</span><input class="search-input" type="number" min="0" name="free_days" value="0"></label>
      <label style="display:grid; gap:6px;"><span class="toolbar-sub">Ставка, ₽/сут.</span><input class="search-input" type="number" min="0" name="rate" value="0"></label>
      <div><button class="btn btn-primary" type="submit">Сохранить</button></div>
    </form>
    <div class="table-wrap" style="max-height:none;">
      <table class="summary-table claims-norms-shipper-table">
        <thead><tr><th>Груз</th><th class="num-col">Бесплатно</th><th class="num-col">Ставка</th><th class="num-col">Действие</th></tr></thead>
        <tbody>
          {% for item in cargo_rules %}
          <tr>
            <td>{{ item.name }}</td>
            <td class="num">{{ item.free_days }}</td>
            <td class="num">{{ item.rate_label }}</td>
            <td class="num">
              <form method="post" action="{{ url_for('claims_ugleuralskaya_norms_delete_cargo') }}" onsubmit="return confirm('Удалить норматив по грузу?');">
                <input type="hidden" name="cargo_name" value="{{ item.name }}">
                <button class="btn btn-secondary" type="submit">Удалить</button>
              </form>
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  </div>
</section>
<section class="card table-card">
  <div class="toolbar"><div><div class="toolbar-title">Нормативы по ранее выгруженному грузу</div><div class="toolbar-sub">Используются для гружёных вагонов после груза</div></div></div>
  <div style="padding:12px; display:grid; gap:12px;">
    <form method="post" action="{{ url_for('claims_ugleuralskaya_norms_upsert_previous_cargo') }}" class="claims-norms-shipper-form">
      <label style="display:grid; gap:6px;"><span class="toolbar-sub">Ранее выгруженный груз</span><input class="search-input" type="text" name="previous_cargo_name" required></label>
      <label style="display:grid; gap:6px;"><span class="toolbar-sub">Бесплатно, сут.</span><input class="search-input" type="number" min="0" name="free_days" value="0"></label>
      <label style="display:grid; gap:6px;"><span class="toolbar-sub">Ставка, ₽/сут.</span><input class="search-input" type="number" min="0" name="rate" value="0"></label>
      <div><button class="btn btn-primary" type="submit">Сохранить</button></div>
    </form>
    <div class="table-wrap" style="max-height:none;">
      <table class="summary-table claims-norms-shipper-table">
        <thead><tr><th>Ранее выгруженный груз</th><th class="num-col">Бесплатно</th><th class="num-col">Ставка</th><th class="num-col">Действие</th></tr></thead>
        <tbody>
          {% for item in previous_cargo_rules %}
          <tr>
            <td>{{ item.name }}</td>
            <td class="num">{{ item.free_days }}</td>
            <td class="num">{{ item.rate_label }}</td>
            <td class="num">
              <form method="post" action="{{ url_for('claims_ugleuralskaya_norms_delete_previous_cargo') }}" onsubmit="return confirm('Удалить норматив по ранее выгруженному грузу?');">
                <input type="hidden" name="previous_cargo_name" value="{{ item.name }}">
                <button class="btn btn-secondary" type="submit">Удалить</button>
              </form>
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  </div>
</section>
</div>
'''

CLAIMS_UGLEURALSKAYA_REASONS_BODY = r'''
<div class="main-tabs">
  <a class="main-tab" href="{{ url_for('index', tab='approach') }}">Подход вагонов</a>
  <a class="main-tab" href="{{ url_for('index', tab='departure') }}">Отправление вагонов</a>
  <a class="main-tab" href="{{ url_for('index', tab='loading') }}">Погрузка</a>
  <a class="main-tab is-active" href="{{ url_for('index', tab='station_idle') }}">Простои</a>
</div>
<div class="sub-tabs">
  <a class="sub-tab" href="{{ url_for('claims_ugleuralskaya_index') }}">Претензии на {{ selected_work_station or selected_station or "Углеуральской" }}</a>
  <a class="sub-tab" href="{{ url_for('claims_ugleuralskaya_norms') }}">Нормативы</a>
  <a class="sub-tab is-active" href="{{ url_for('claims_ugleuralskaya_reasons') }}">Комментарии</a>
</div>
<section class="card topbar">
  <div class="topbar-left">
    <div class="title">Формализованные комментарии</div>
    <div class="meta">Список значений для вкладки «Претензии на {{ selected_work_station or selected_station or "Углеуральской" }}»</div>
  </div>
  <div class="topbar-right"><a class="btn btn-secondary" href="{{ url_for('claims_ugleuralskaya_index') }}">Назад</a></div>
</section>
{% if success_message %}<div class="success card">{{ success_message }}</div>{% endif %}
{% if error_message %}<div class="error card">{{ error_message }}</div>{% endif %}
<section class="card" style="padding:12px; display:grid; gap:12px;">
  <form method="post" action="{{ url_for('claims_ugleuralskaya_reasons_add') }}" style="display:flex; gap:8px; flex-wrap:wrap; align-items:flex-end;">
    <label style="display:grid; gap:6px; min-width:320px; flex:1;"><span class="toolbar-sub">Новый комментарий</span><input class="search-input" type="text" name="reason" required></label>
    <button class="btn btn-primary" type="submit">Добавить</button>
  </form>
  <div class="table-wrap" style="max-height:none;">
    <table class="summary-table">
      <thead><tr><th>Комментарий</th><th style="width:180px;">Изменить</th><th style="width:150px;">Удалить</th></tr></thead>
      <tbody>
        {% for item in reasons %}
        <tr>
          <td>{{ item }}</td>
          <td>
            <form method="post" action="{{ url_for('claims_ugleuralskaya_reasons_update') }}" style="display:grid; gap:6px;">
              <input type="hidden" name="old_reason" value="{{ item }}">
              <input class="search-input" type="text" name="new_reason" value="{{ item }}">
              <button class="btn btn-secondary" type="submit">Сохранить</button>
            </form>
          </td>
          <td>
            <form method="post" action="{{ url_for('claims_ugleuralskaya_reasons_delete') }}" onsubmit="return confirm('Удалить комментарий?');">
              <input type="hidden" name="reason" value="{{ item }}">
              <button class="btn btn-secondary" type="submit">Удалить</button>
            </form>
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</section>
'''
