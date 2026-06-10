from __future__ import annotations

IDLE_COMMENTS_INDEX_BODY = r'''
<div class="main-tabs">
  <a class="main-tab" href="{{ url_for('index', tab='approach') }}">Подход вагонов</a>
  <a class="main-tab" href="{{ url_for('index', tab='departure') }}">Отправление вагонов</a>
  <a class="main-tab" href="{{ url_for('index', tab='loading') }}">Погрузка</a>
  <a class="main-tab is-active" href="{{ url_for('index', tab='station_idle') }}">Простои</a>
  <a class="main-tab" href="{{ url_for('index', tab='raw_material') }}">Сырье</a>
  <a class="main-tab" href="{{ url_for('technical_state_index') }}">Техническое состояние</a>
  <a class="main-tab" href="{{ url_for('index', tab='manual_filter') }}">Ручной фильтр</a>
  <a class="main-tab" href="{{ url_for('archive_search') }}">Архив</a>
  <a class="main-tab" href="{{ url_for('mailing_rules') }}">Авторассылка справок</a>
</div>

<div class="sub-tabs">
  <a class="sub-tab" href="{{ url_for('index', tab='station_idle', idle_view='ugleuralskaya') }}">Простой на станции {{ selected_station or "Углеуральская" }}</a>
  <a class="sub-tab" href="{{ url_for('index', tab='station_idle', idle_view='destination') }}">Простой на станции назначения</a>
  <a class="sub-tab is-active" href="{{ url_for('idle_comments_index', archive_date=archive_date if archive_date else None) }}">Простой с комментариями</a>
  <a class="sub-tab" href="{{ url_for('claims_ugleuralskaya_index') }}">Претензии на {{ selected_station or "Углеуральской" }}</a>
</div>

<section class="card topbar">
  <div class="topbar-left">
    <div class="title">{{ app_title }} — Простой с комментариями</div>
    <div class="meta">
      {{ source_name }}
      {% if source_time %} • {{ source_time }}{% endif %}
      {% if report_date_label %} • Дата справки: {{ report_date_label }}{% endif %}
      {% if archive_date %} • Архив комментариев: {{ archive_date }}{% endif %}
    </div>
  </div>
  <div class="topbar-right" style="margin-left:auto; align-items:flex-start;">
    <form class="search-form" method="get" action="{{ url_for('idle_comments_search') }}" style="display:flex; gap:6px; align-items:center; flex-wrap:wrap; width:auto; justify-content:flex-end; margin-left:auto;">
      <input class="search-input" type="text" name="wagon" value="{{ search_wagon }}" placeholder="Номер вагона" style="max-width:170px;">
      <input class="archive-date" type="date" name="date_from" value="{{ search_date_from }}" title="Дата с">
      <input class="archive-date" type="date" name="date_to" value="{{ search_date_to }}" title="Дата по">
      <button class="btn btn-soft" type="submit">Поиск</button>
      {% if search_wagon or search_date_from or search_date_to %}<a class="btn btn-secondary" href="{{ url_for('idle_comments_index') }}">Сбросить</a>{% endif %}
    </form>
    <form class="archive-form" method="get" action="{{ url_for('idle_comments_index') }}">
      <input class="archive-date" type="date" name="archive_date" value="{{ archive_date }}">
      <button class="btn btn-soft" type="submit">Загрузить из архива</button>
      {% if archive_date %}<a class="btn btn-secondary" href="{{ url_for('idle_comments_index') }}">Текущая</a>{% endif %}
    </form>
    <a class="btn btn-secondary" href="{{ url_for('idle_comments_index') }}">Обновить</a>
    <a class="btn btn-soft" href="{{ url_for('idle_comments_reasons') }}">Причины простоя</a>
  </div>
</section>

{% if success_message %}<div class="success card">{{ success_message }}</div>{% endif %}
{% if error_message %}<div class="error card">{{ error_message }}</div>{% endif %}

<div class="header-grid">
  {% for item in metric_cards %}
  <section class="card metric {% if item.danger %}metric-danger{% endif %}">
    <div class="label">{{ item.label }}</div>
    <div class="value">{{ item.count }}</div>
    {% if item.sub %}<div class="sub">{{ item.sub }}</div>{% endif %}
  </section>
  {% endfor %}
</div>

<section class="card table-card">
  <div class="toolbar">
    <div>
      <div class="toolbar-title">Простой с комментариями</div>
      <div class="toolbar-sub">Сводка построена по логике вкладки «Простой на станции {{ selected_station or "Углеуральская" }}»</div>
    </div>
  </div>
  <div class="table-wrap">
    <table class="summary-table">
      <thead>
        <tr>
          <th rowspan="2" class="c-name">Интервал</th>
          {% for category in category_order %}
          <th colspan="2" class="num-col group-split">{{ category }}</th>
          {% endfor %}
        </tr>
        <tr>
          {% for category in category_order %}
            {% for cargo in cargo_order %}
            <th class="num-col {% if cargo == 'гр' %}group-split{% else %}cargo-split{% endif %}">{{ cargo }}</th>
            {% endfor %}
          {% endfor %}
        </tr>
      </thead>
      <tbody>
        {% for row in rows %}
        <tr class="{% if row.level == 'total' %}row-total{% else %}row-station{% endif %}">
          <td class="c-name">{{ row.label }}</td>
          {% for category in category_order %}
            {% for cargo in cargo_order %}
            {% set cell = row.counts[category][cargo] %}
            {% set link = row.links[category][cargo] if cell else None %}
            <td class="num {% if cargo == 'гр' %}group-split{% else %}cargo-split{% endif %}">
              {% if link %}<a href="{{ link }}">{{ cell }}</a>{% else %}{{ cell }}{% endif %}
            </td>
            {% endfor %}
          {% endfor %}
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</section>

<script>
(function(){
  const table = document.getElementById('idle-comments-table');
  if (!table) return;
  const tbody = table.tBodies[0];
  const rows = Array.from(tbody.rows);
  const buttons = Array.from(table.querySelectorAll('.col-filter-btn'));
  const hiddenExport = document.getElementById('idle-comments-filtered-rows');
  const activeFilters = new Map();
  let popover = null;
  let activeIndex = null;

  function cellText(row, index){
    const cell = row.cells[index];
    if (!cell) return '';
    const input = cell.querySelector('input.comment-input');
    if (input) return (input.value || '').trim();
    return (cell.innerText || cell.textContent || '').trim();
  }

  function syncRowJson(row){
    const payload = row.dataset.rowJson ? JSON.parse(row.dataset.rowJson) : {};
    payload.comment_text = cellText(row, 14);
    payload.comment_updated_at = cellText(row, 13);
    row.dataset.rowJson = JSON.stringify(payload);
    return payload;
  }

  function visiblePayload(){
    return rows.filter((row) => row.style.display !== 'none').map(syncRowJson);
  }

  function updateExportPayload(){
    if (hiddenExport) hiddenExport.value = JSON.stringify(visiblePayload());
  }

  function uniqueValues(index){
    const values = new Set();
    rows.forEach((row) => values.add(cellText(row, index)));
    return Array.from(values).sort((a,b) => a.localeCompare(b, 'ru', {numeric:true, sensitivity:'base'}));
  }

  function applyFilters(){
    rows.forEach((row) => {
      let visible = true;
      activeFilters.forEach((allowed, index) => {
        if (!allowed || !allowed.size) return;
        if (!allowed.has(cellText(row, Number(index)))) visible = false;
      });
      row.style.display = visible ? '' : 'none';
    });
    buttons.forEach((btn) => {
      const idx = btn.dataset.colIndex;
      btn.classList.toggle('is-active', activeFilters.has(idx) && activeFilters.get(idx)?.size);
    });
    updateExportPayload();
  }

  function closePopover(){
    if (popover) popover.remove();
    popover = null;
    activeIndex = null;
  }

  function openPopover(button){
    const index = button.dataset.colIndex;
    if (popover && activeIndex === index){ closePopover(); return; }
    closePopover();
    activeIndex = index;
    const values = uniqueValues(Number(index));
    const current = new Set(activeFilters.get(index) || values);
    popover = document.createElement('div');
    popover.className = 'filter-popover';
    popover.innerHTML = `
      <div style="display:grid; gap:8px;">
        <input type="search" class="search-input" placeholder="Поиск">
        <div style="display:flex; gap:8px; flex-wrap:wrap;">
          <button type="button" class="btn btn-soft" data-action="all">Выбрать всё</button>
          <button type="button" class="btn btn-secondary" data-action="none">Снять всё</button>
          <button type="button" class="btn btn-secondary" data-action="reset">Сброс</button>
        </div>
        <div class="filter-options" style="display:grid; gap:6px; max-height:220px; overflow:auto;"></div>
        <div style="display:flex; justify-content:flex-end; gap:8px;">
          <button type="button" class="btn btn-secondary" data-action="cancel">Отмена</button>
          <button type="button" class="btn btn-primary" data-action="apply">Применить</button>
        </div>
      </div>`;
    document.body.appendChild(popover);
    const rect = button.getBoundingClientRect();
    const margin = 12;
    const width = popover.offsetWidth || 320;
    const height = popover.offsetHeight || 320;
    let left = rect.right - width;
    left = Math.max(margin, Math.min(left, window.innerWidth - width - margin));
    let top = rect.bottom + 8;
    if (top + height > window.innerHeight - margin) top = rect.top - height - 8;
    if (top < margin) top = margin;
    popover.style.top = `${top}px`;
    popover.style.left = `${left}px`;
    const optionsBox = popover.querySelector('.filter-options');
    const search = popover.querySelector('input[type="search"]');

    function renderOptions(query=''){
      const q = query.trim().toLowerCase();
      optionsBox.innerHTML = '';
      values.filter((value) => value.toLowerCase().includes(q)).forEach((value) => {
        const label = document.createElement('label');
        label.style.display = 'flex';
        label.style.gap = '8px';
        label.style.alignItems = 'flex-start';
        label.innerHTML = `<input type="checkbox" value="${value.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}" ${current.has(value) ? 'checked' : ''}><span style="word-break:break-word;">${value || '∅ Пусто'}</span>`;
        optionsBox.appendChild(label);
      });
    }

    renderOptions();
    search.addEventListener('input', () => renderOptions(search.value));
    popover.addEventListener('click', (event) => {
      const action = event.target?.dataset?.action;
      if (!action) return;
      if (action === 'all'){ current.clear(); values.forEach((value) => current.add(value)); renderOptions(search.value); return; }
      if (action === 'none'){ current.clear(); renderOptions(search.value); return; }
      if (action === 'reset'){ activeFilters.delete(index); applyFilters(); closePopover(); return; }
      if (action === 'cancel'){ closePopover(); return; }
      if (action === 'apply'){
        const checked = new Set(Array.from(optionsBox.querySelectorAll('input[type="checkbox"]:checked')).map((node) => node.value));
        if (checked.size === values.length) activeFilters.delete(index);
        else activeFilters.set(index, checked);
        applyFilters();
        closePopover();
      }
    });
  }

  buttons.forEach((button) => button.addEventListener('click', (event) => { event.preventDefault(); openPopover(button); }));
  document.addEventListener('click', (event) => { if (!popover) return; if (popover.contains(event.target)) return; if (event.target.closest('.col-filter-btn')) return; closePopover(); });
  tbody.addEventListener('input', (event) => { if (event.target.matches('input.comment-input')) updateExportPayload(); });
  updateExportPayload();
})();
</script>
'''

IDLE_COMMENTS_DETAIL_BODY = r'''
<div class="breadcrumb">
  <a href="{{ back_url or url_for('idle_comments_index', archive_date=archive_date if archive_mode else None) }}">Назад к сводке</a>
  <span>•</span>
  <span>Простой с комментариями</span>
</div>

{% if success_message %}<div class="success card">{{ success_message }}</div>{% endif %}
{% if error_message %}<div class="error card">{{ error_message }}</div>{% endif %}

<section class="card detail-head">
  <div>
    <h1 class="detail-title">Детализация — простой с комментариями</h1>
    <div class="toolbar-sub">{{ filter_caption }}</div>
  </div>
  <div class="chips">
    <span class="chip">Всего: {{ total_count }}</span>
    {% if archive_mode %}<span class="chip">Архив: {{ archive_date }}</span>{% endif %}
    <a class="btn btn-soft" href="{{ url_for('idle_comments_reasons') }}">Причины простоя</a>
  </div>
</section>

<section class="card table-card">
  <div class="toolbar">
    <div><div class="toolbar-title">Детализация</div></div>
    <div class="toolbar-right" style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
      <span class="badge">Редактируемые поля доступны только в текущей версии</span>
      <button class="btn btn-soft" type="submit" form="idle-comments-export-form">Скачать Excel</button>
    </div>
  </div>
  <form id="idle-comments-export-form" method="post" action="{{ url_for('idle_comments_export') }}" style="display:none;">
    <input type="hidden" name="idle_bucket" value="{{ idle_bucket or '' }}">
    <input type="hidden" name="kind" value="{{ kind or '' }}">
    <input type="hidden" name="cargo" value="{{ cargo or '' }}">
    <input type="hidden" name="archive_date" value="{{ export_archive_date or '' }}">
    <input type="hidden" name="filtered_rows" id="idle-comments-filtered-rows" value="">
  </form>
  <div class="table-wrap">
    <form method="post" action="{{ url_for('idle_comments_save') }}" id="idle-comments-save-form">
      <input type="hidden" name="idle_bucket" value="{{ idle_bucket or '' }}">
      <input type="hidden" name="kind" value="{{ kind or '' }}">
      <input type="hidden" name="cargo" value="{{ cargo or '' }}">
      <table class="detail-table" id="idle-comments-table" style="min-width:2100px;">
        <thead>
          <tr>
            {% if show_report_date %}<th data-col-key="report_date_display"><div class="th-wrap"><span>Дата справки</span><button type="button" class="col-filter-btn" data-col-key="report_date_display">▾</button></div></th>{% endif %}
            <th data-col-key="wagon_number"><div class="th-wrap"><span>№ ваг.</span><button type="button" class="col-filter-btn" data-col-key="wagon_number">▾</button></div></th>
            <th data-col-key="raw_kind"><div class="th-wrap"><span>Род ваг.</span><button type="button" class="col-filter-btn" data-col-key="raw_kind">▾</button></div></th>
            <th data-col-key="trip_start"><div class="th-wrap"><span>Нач. рейса</span><button type="button" class="col-filter-btn" data-col-key="trip_start">▾</button></div></th>
            <th data-col-key="trip_end"><div class="th-wrap"><span>Дата и время окончания рейса</span><button type="button" class="col-filter-btn" data-col-key="trip_end">▾</button></div></th>
            <th data-col-key="origin_road"><div class="th-wrap"><span>Дор. отпр.</span><button type="button" class="col-filter-btn" data-col-key="origin_road">▾</button></div></th>
            <th data-col-key="origin_station"><div class="th-wrap"><span>Ст. отпр.</span><button type="button" class="col-filter-btn" data-col-key="origin_station">▾</button></div></th>
            <th data-col-key="destination_road"><div class="th-wrap"><span>Дор. назн.</span><button type="button" class="col-filter-btn" data-col-key="destination_road">▾</button></div></th>
            <th data-col-key="destination"><div class="th-wrap"><span>Ст. назн.</span><button type="button" class="col-filter-btn" data-col-key="destination">▾</button></div></th>
            <th data-col-key="cargo_name"><div class="th-wrap"><span>Груз</span><button type="button" class="col-filter-btn" data-col-key="cargo_name">▾</button></div></th>
            <th data-col-key="previous_cargo"><div class="th-wrap"><span>Ранее выгруженный груз</span><button type="button" class="col-filter-btn" data-col-key="previous_cargo">▾</button></div></th>
            <th data-col-key="weight_kg"><div class="th-wrap"><span>Вес, кг</span><button type="button" class="col-filter-btn" data-col-key="weight_kg">▾</button></div></th>
            <th data-col-key="station"><div class="th-wrap"><span>Ст. опер.</span><button type="button" class="col-filter-btn" data-col-key="station">▾</button></div></th>
            <th data-col-key="operation"><div class="th-wrap"><span>Опер.</span><button type="button" class="col-filter-btn" data-col-key="operation">▾</button></div></th>
            <th data-col-key="operation_time"><div class="th-wrap"><span>Дата/время опер.</span><button type="button" class="col-filter-btn" data-col-key="operation_time">▾</button></div></th>
            <th data-col-key="idle_time"><div class="th-wrap"><span>Простой, сут.</span><button type="button" class="col-filter-btn" data-col-key="idle_time">▾</button></div></th>
            <th data-col-key="comment_updated_at"><div class="th-wrap"><span>Дата и время</span><button type="button" class="col-filter-btn" data-col-key="comment_updated_at">▾</button></div></th>
            <th data-col-key="comment_text"><div class="th-wrap"><span>Примечание</span><button type="button" class="col-filter-btn" data-col-key="comment_text">▾</button></div></th>
          </tr>
        </thead>
        <tbody>
          {% for item in records %}
          <tr data-row-json='{{ item|tojson|forceescape }}'>
            {% if show_report_date %}<td>{{ item.report_date_display or '' }}</td>{% endif %}
            <td class="mono">{{ item.wagon_number }}</td>
            <td>{{ item.raw_kind }}</td>
            <td>{{ item.trip_start }}</td>
            <td>{{ item.trip_end }}</td>
            <td>{{ item.origin_road }}</td>
            <td>{{ item.origin_station }}</td>
            <td>{{ item.destination_road }}</td>
            <td>{{ item.destination }}</td>
            <td>{{ item.cargo_name }}</td>
            <td>{{ item.previous_cargo }}</td>
            <td class="num">{{ item.weight_kg }}</td>
            <td>{{ item.station }}</td>
            <td>{{ item.operation }}</td>
            <td>{{ item.operation_time }}</td>
            <td>{{ item.idle_time }}</td>
            <td>{{ item.comment_updated_at }}</td>
            <td>
              {% if archive_mode %}
                {{ item.comment_text }}
              {% else %}
                <input type="hidden" name="wagon_number" value="{{ item.wagon_number }}">
                <input type="text" name="comment_text" value="{{ item.comment_text }}" list="idle-reasons-list" class="comment-input" style="width:100%; min-width:280px; border:1px solid #dce4ee; border-radius:8px; min-height:30px; padding:0 8px;">
              {% endif %}
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
      {% if not archive_mode %}
      <div style="padding:10px 12px; display:flex; gap:8px; justify-content:flex-end; border-top:1px solid #edf2f7;">
        <button class="btn btn-primary" type="submit">Сохранить изменения</button>
      </div>
      <datalist id="idle-reasons-list">
        {% for item in reasons %}<option value="{{ item }}"></option>{% endfor %}
      </datalist>
      {% endif %}
    </form>
  </div>
</section>

<script>
(function(){
  const table = document.getElementById('idle-comments-table');
  if (!table) return;
  const tbody = table.tBodies[0];
  const rows = Array.from(tbody.rows);
  const buttons = Array.from(table.querySelectorAll('.col-filter-btn'));
  const hiddenExport = document.getElementById('idle-comments-filtered-rows');
  const activeFilters = new Map();
  const keyOrder = Array.from(table.tHead.rows[0].cells).map((cell) => cell.querySelector('.col-filter-btn')?.dataset.colKey || cell.dataset.colKey || '');
  const commentIndex = keyOrder.indexOf('comment_text');
  const updatedIndex = keyOrder.indexOf('comment_updated_at');
  let popover = null;
  let activeKey = null;

  function indexByKey(key){ return keyOrder.indexOf(key); }

  function cellText(row, key){
    const index = indexByKey(key);
    const cell = index >= 0 ? row.cells[index] : null;
    if (!cell) return '';
    const input = cell.querySelector('input.comment-input');
    if (input) return (input.value || '').trim();
    return (cell.innerText || cell.textContent || '').trim();
  }

  function syncRowJson(row){
    const payload = row.dataset.rowJson ? JSON.parse(row.dataset.rowJson) : {};
    if (commentIndex >= 0) payload.comment_text = cellText(row, 'comment_text');
    if (updatedIndex >= 0) payload.comment_updated_at = cellText(row, 'comment_updated_at');
    row.dataset.rowJson = JSON.stringify(payload);
    return payload;
  }

  function visiblePayload(){
    return rows.filter((row) => row.style.display !== 'none').map(syncRowJson);
  }

  function updateExportPayload(){
    if (hiddenExport) hiddenExport.value = JSON.stringify(visiblePayload());
  }

  function rowMatches(row, excludeKey){
    let visible = true;
    activeFilters.forEach((allowed, key) => {
      if (excludeKey !== undefined && String(key) === String(excludeKey)) return;
      if (!allowed || !allowed.size) return;
      if (!allowed.has(cellText(row, key))) visible = false;
    });
    return visible;
  }

  function uniqueValues(key){
    const values = new Set();
    rows.forEach((row) => { if (rowMatches(row, key)) values.add(cellText(row, key)); });
    return Array.from(values).sort((a,b) => a.localeCompare(b, 'ru', {numeric:true, sensitivity:'base'}));
  }

  function applyFilters(){
    rows.forEach((row) => {
      row.style.display = rowMatches(row) ? '' : 'none';
    });
    buttons.forEach((btn) => {
      const key = btn.dataset.colKey;
      btn.classList.toggle('is-active', activeFilters.has(key) && activeFilters.get(key)?.size);
    });
    updateExportPayload();
  }

  function closePopover(){ if (popover) popover.remove(); popover = null; activeKey = null; }

  function openPopover(button){
    const key = button.dataset.colKey;
    if (popover && activeKey === key){ closePopover(); return; }
    closePopover();
    activeKey = key;
    const values = uniqueValues(key);
    const current = activeFilters.has(key) ? new Set(Array.from(activeFilters.get(key) || []).filter((value) => values.includes(value))) : new Set(values);
    popover = document.createElement('div');
    popover.className = 'filter-popover';
    popover.innerHTML = `
      <div style="display:grid; gap:8px;">
        <input type="search" class="search-input" placeholder="Поиск">
        <div style="display:flex; gap:8px; flex-wrap:wrap;">
          <button type="button" class="btn btn-soft" data-action="all">Выбрать всё</button>
          <button type="button" class="btn btn-secondary" data-action="none">Снять всё</button>
          <button type="button" class="btn btn-secondary" data-action="reset">Сброс</button>
        </div>
        <div class="filter-options" style="display:grid; gap:6px; max-height:220px; overflow:auto;"></div>
        <div style="display:flex; justify-content:flex-end; gap:8px;">
          <button type="button" class="btn btn-secondary" data-action="cancel">Отмена</button>
          <button type="button" class="btn btn-primary" data-action="apply">Применить</button>
        </div>
      </div>`;
    document.body.appendChild(popover);
    const rect = button.getBoundingClientRect();
    const margin = 12;
    const width = popover.offsetWidth || 320;
    const height = popover.offsetHeight || 320;
    let left = rect.right - width;
    left = Math.max(margin, Math.min(left, window.innerWidth - width - margin));
    let top = rect.bottom + 8;
    if (top + height > window.innerHeight - margin) top = rect.top - height - 8;
    if (top < margin) top = margin;
    popover.style.top = `${top}px`;
    popover.style.left = `${left}px`;
    const optionsBox = popover.querySelector('.filter-options');
    const search = popover.querySelector('input[type="search"]');

    function renderOptions(query=''){
      const q = query.trim().toLowerCase();
      optionsBox.innerHTML = '';
      values.filter((value) => value.toLowerCase().includes(q)).forEach((value) => {
        const label = document.createElement('label');
        label.style.display = 'flex';
        label.style.gap = '8px';
        label.style.alignItems = 'flex-start';
        label.innerHTML = `<input type="checkbox" value="${value.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}" ${current.has(value) ? 'checked' : ''}><span style="word-break:break-word;">${value || '∅ Пусто'}</span>`;
        optionsBox.appendChild(label);
      });
    }

    renderOptions();
    search.addEventListener('input', () => renderOptions(search.value));
    popover.addEventListener('click', (event) => {
      const action = event.target?.dataset?.action;
      if (!action) return;
      if (action === 'all'){ current.clear(); values.forEach((value) => current.add(value)); renderOptions(search.value); return; }
      if (action === 'none'){ current.clear(); renderOptions(search.value); return; }
      if (action === 'reset'){ activeFilters.delete(key); applyFilters(); closePopover(); return; }
      if (action === 'cancel'){ closePopover(); return; }
      if (action === 'apply'){
        const checked = new Set(Array.from(optionsBox.querySelectorAll('input[type="checkbox"]:checked')).map((node) => node.value));
        if (checked.size === values.length) activeFilters.delete(key);
        else activeFilters.set(key, checked);
        applyFilters();
        closePopover();
      }
    });
  }

  buttons.forEach((button) => button.addEventListener('click', (event) => { event.preventDefault(); openPopover(button); }));
  document.addEventListener('click', (event) => { if (!popover) return; if (popover.contains(event.target)) return; if (event.target.closest('.col-filter-btn')) return; closePopover(); });
  tbody.addEventListener('input', (event) => { if (event.target.matches('input.comment-input')) updateExportPayload(); });
  updateExportPayload();
})();
</script>
'''

IDLE_COMMENTS_REASONS_BODY = r'''
<div class="breadcrumb">
  <a href="{{ url_for('idle_comments_index') }}">Назад к вкладке «Простой с комментариями»</a>
</div>

{% if success_message %}<div class="success card">{{ success_message }}</div>{% endif %}
{% if error_message %}<div class="error card">{{ error_message }}</div>{% endif %}

<section class="card detail-head">
  <div>
    <h1 class="detail-title">Причины простоя</h1>
    <div class="toolbar-sub">Справочник причин для выпадающего списка в колонке «Примечание»</div>
  </div>
</section>

<section class="card" style="padding:12px; display:grid; gap:12px;">
  <form method="post" action="{{ url_for('idle_comments_reasons_add') }}" style="display:flex; gap:8px; flex-wrap:wrap; align-items:end;">
    <div style="flex:1 1 420px;">
      <div class="search-caption">Новая причина</div>
      <input class="search-input" type="text" name="reason" required placeholder="Например: ожидание выгрузки">
    </div>
    <button class="btn btn-primary" type="submit">Добавить</button>
  </form>

  <div class="table-wrap" style="max-height:none;">
    <table class="summary-table" style="table-layout:auto;">
      <thead><tr><th>Причина</th><th style="width:260px;">Действия</th></tr></thead>
      <tbody>
        {% for item in reasons %}
        <tr>
          <td>{{ item }}</td>
          <td>
            <form method="post" action="{{ url_for('idle_comments_reasons_update') }}" style="display:flex; gap:8px; flex-wrap:wrap;">
              <input type="hidden" name="old_reason" value="{{ item }}">
              <input class="search-input" type="text" name="new_reason" value="{{ item }}" style="max-width:240px; height:30px;">
              <button class="btn btn-soft" type="submit">Изменить</button>
            </form>
            <form method="post" action="{{ url_for('idle_comments_reasons_delete') }}" style="margin-top:6px;">
              <input type="hidden" name="reason" value="{{ item }}">
              <button class="btn btn-secondary" type="submit">Удалить</button>
            </form>
          </td>
        </tr>
        {% else %}
        <tr><td colspan="2">Причины ещё не добавлены.</td></tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</section>


'''
