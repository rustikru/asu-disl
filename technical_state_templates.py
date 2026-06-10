TECHNICAL_STATE_BODY = """
<div class="main-tabs">
  <a class="main-tab {% if current_tab == 'approach' %}is-active{% endif %}" href="{{ url_for('index', tab='approach') }}">Подход вагонов</a>
  <a class="main-tab {% if current_tab == 'departure' %}is-active{% endif %}" href="{{ url_for('index', tab='departure') }}">Отправление вагонов</a>
  <a class="main-tab {% if current_tab == 'loading' %}is-active{% endif %}" href="{{ url_for('index', tab='loading') }}">Погрузка</a>
  <a class="main-tab {% if current_tab == 'station_idle' %}is-active{% endif %}" href="{{ url_for('index', tab='station_idle') }}">Простои</a>
  <a class="main-tab {% if current_tab == 'raw_material' %}is-active{% endif %}" href="{{ url_for('index', tab='raw_material') }}">Сырье</a>
  <a class="main-tab {% if current_tab == 'technical_state' %}is-active{% endif %}" href="{{ url_for('technical_state_index') }}">Техническое состояние</a>
  <a class="main-tab {% if current_tab == 'manual_filter' %}is-active{% endif %}" href="{{ url_for('index', tab='manual_filter') }}">Ручной фильтр</a>
  <a class="main-tab {% if current_tab == 'archive' %}is-active{% endif %}" href="{{ url_for('archive_search') }}">Архив</a>
  <a class="main-tab {% if current_tab == 'mailing' %}is-active{% endif %}" href="{{ url_for('mailing_rules') }}">Авторассылка справок</a>
</div>

<section class="card topbar">
  <div class="topbar-left">
    <div class="title">АСУ Подход — Техническое состояние</div>
    <div class="meta">{{ source_meta }}{% if source_time %} • {{ source_time }}{% endif %}</div>
  </div>
  <div class="topbar-right" style="display:flex; gap:8px; align-items:center; flex-wrap:wrap; justify-content:flex-end;">
    <form class="search-form" method="get" action="{{ url_for('technical_state_search') }}" style="display:flex; gap:6px; align-items:center; flex-wrap:wrap; justify-content:flex-end;">
      <input class="search-input" type="text" name="wagon" value="{{ search_wagon }}" placeholder="Введите один или несколько номеров вагонов" autocomplete="off" required>
      <button class="btn btn-primary" type="submit">Найти</button>
      {% if search_wagon %}<a class="btn btn-secondary" href="{{ url_for('technical_state_index') }}">Сбросить</a>{% endif %}
    </form>
  </div>
</section>

{% if success_message %}<div class="success card">{{ success_message }}</div>{% endif %}
{% if error_message %}<div class="error card">{{ error_message }}</div>{% endif %}

{% if wagon_search_summary %}
<section class="card" style="margin-bottom:12px;">
  <div class="toolbar">
    <div>
      <div class="toolbar-title">Результат поиска по вагонам</div>
      <div class="toolbar-sub">Запрошено {{ wagon_search_summary.requested_count }} вагонов, найдено {{ wagon_search_summary.found_count }} вагонов.</div>
      {% if wagon_search_summary.missing_wagons %}
      <div class="toolbar-sub" style="margin-top:8px; word-break:break-word;"><strong>Нет информации:</strong> {{ wagon_search_summary.missing_wagons | join(', ') }}</div>
      {% endif %}
    </div>
  </div>
</section>
{% endif %}

<section class="card detail-head">
  <div>
    <h1 class="detail-title" style="max-width:100%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">Техническое состояние</h1>
    <div class="toolbar-sub" style="max-width:100%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">Детализация по данным approach и departure</div>
  </div>
  <div class="chips">
    <span class="chip">Всего: {{ total_count }}</span>
    <form method="post" action="{{ url_for('technical_state_export') }}" id="technical-state-export-form" style="display:none;">
      <input type="hidden" name="filtered_rows" id="technical-state-filtered-rows" value="">
      <input type="hidden" name="wagon" value="{{ search_wagon }}">
      <input type="hidden" name="active_filters" id="technical-state-active-filters" value="">
    </form>
    <button class="btn btn-soft" type="submit" form="technical-state-export-form">Excel</button>
  </div>
</section>

<section class="card table-card">
  <div class="toolbar">
    <div><div class="toolbar-title">Детализация</div></div>
    <div class="toolbar-right">
      <span class="badge" id="technical-visible-count-badge">Показано: {{ total_count }}</span>
      <button class="btn btn-ghost" type="button" id="clear-technical-filters">Сбросить фильтры</button>
    </div>
  </div>
  {% if records %}
  <div class="table-wrap technical-state-wrap">
    <table class="detail-table technical-state-table" id="technical-state-table">
      <thead>
        <tr>
          {% for header in headers %}
          <th data-col-index="{{ loop.index0 }}">
            <div class="th-wrap">
              <span style="display:block; max-width:100%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">{{ header }}</span>
              <button type="button" class="col-filter-btn" data-col-index="{{ loop.index0 }}">▾</button>
            </div>
          </th>
          {% endfor %}
        </tr>
      </thead>
      <tbody>
        {% for item in records %}
        <tr data-detail-row="1">
          {% for value in item.cells %}
          <td{% if loop.index0 == 0 %} class="mono"{% endif %} title="{{ value }}"><div style="max-width:100%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">{{ value }}</div></td>
          {% endfor %}
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% else %}
  <div class="empty">Нет данных для отображения. Загрузите актуальные справки approach и departure.</div>
  {% endif %}
</section>

<script>
(function(){
  const table = document.getElementById('technical-state-table');
  if (!table) return;
  const rows = Array.from(table.querySelectorAll('tbody tr[data-detail-row="1"]'));
  const buttons = Array.from(table.querySelectorAll('.col-filter-btn'));
  const clearBtn = document.getElementById('clear-technical-filters');
  const visibleBadge = document.getElementById('technical-visible-count-badge');
  const exportForm = document.getElementById('technical-state-export-form');
  const filteredRowsInput = document.getElementById('technical-state-filtered-rows');
  const activeFiltersInput = document.getElementById('technical-state-active-filters');
  const headers = Array.from(table.querySelectorAll('thead th[data-col-index]')).map(function(th){
    const title = th.querySelector('.th-wrap span');
    return title ? title.textContent.replace(/\\s+/g, ' ').trim() : th.textContent.replace(/\\s+/g, ' ').trim();
  });
  const active = {};
  let popover = null;
  function getCellText(row, colIndex) { const cell = row.children[colIndex]; return cell ? cell.textContent.replace(/\\s+/g, ' ').trim() : ''; }
  function rowMatches(row, excludeKey) { for (const key in active) { if (excludeKey !== undefined && String(key) === String(excludeKey)) continue; const allowed = active[key]; if (!allowed) continue; if (allowed.size === 0) return false; if (!allowed.has(getCellText(row, Number(key)))) return false; } return true; }
  function syncExportPayload() {
    if (filteredRowsInput) filteredRowsInput.value = '';
    if (!activeFiltersInput) return;
    const payload = {};
    Object.keys(active).forEach(function(key){
      payload[key] = Array.from(active[key] || []);
    });
    activeFiltersInput.value = JSON.stringify(payload);
  }
  function applyFilters() {
    let visible = 0;
    rows.forEach(function(row){
      const show = rowMatches(row);
      row.style.display = show ? '' : 'none';
      if (show) visible += 1;
    });
    if (visibleBadge) visibleBadge.textContent = 'Показано: ' + visible;
    buttons.forEach(function(btn){
      const idx = btn.getAttribute('data-col-index');
      btn.classList.toggle('is-active', !!(active[idx] !== undefined));
    });
    syncExportPayload();
  }

  function availableValues(colIndex) {
    const values = new Set();
    const key = String(colIndex);
    rows.forEach(function(row){ if (rowMatches(row, key)) values.add(getCellText(row, colIndex)); });
    return Array.from(values).sort(function(a, b){ return a.localeCompare(b, 'ru'); });
  }
  function closePopover() {
    if (popover) { popover.remove(); popover = null; }
  }
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
  function renderFilterList(list, values, selected, key, query){
    const q = (query || '').trim().toLowerCase();
    list.innerHTML = '';
    const filtered = values.filter(function(value){ return !q || (value || '').toLowerCase().includes(q); });
    if (!filtered.length) {
      const empty = document.createElement('div'); empty.className = 'filter-empty'; empty.textContent = 'Нет значений'; list.appendChild(empty); return;
    }
    filtered.forEach(function(value){
      const label = document.createElement('label'); label.className = 'filter-item';
      const checkbox = document.createElement('input'); checkbox.type = 'checkbox'; checkbox.value = value; checkbox.checked = selected.has(value);
      checkbox.addEventListener('change', function(){
        if (checkbox.checked) selected.add(value); else selected.delete(value);
        active[key] = new Set(selected); applyFilters();
      });
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
  buttons.forEach(function(button){
    button.addEventListener('click', function(event){
      event.stopPropagation();
      const colIndex = Number(button.getAttribute('data-col-index'));
      openPopover(button, colIndex);
    });
  });
  if (clearBtn) clearBtn.addEventListener('click', function(){
    Object.keys(active).forEach(function(key){ delete active[key]; });
    applyFilters(); closePopover();
  });
  if (exportForm) exportForm.addEventListener('submit', syncExportPayload);
  document.addEventListener('click', function(event){
    if (!popover) return;
    if (popover.contains(event.target)) return;
    if (event.target.closest('.col-filter-btn')) return;
    closePopover();
  });

  rows.forEach(function(row){
    row.addEventListener('click', function(event){
      const target = event.target;
      if (target && target.closest('a, button, input, select, textarea, label')) return;
      rows.forEach(function(item){ if (item !== row) item.classList.remove('asu-selected-row'); });
      row.classList.toggle('asu-selected-row');
    });
  });

  applyFilters();
})();
</script>
"""
