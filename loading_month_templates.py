from __future__ import annotations

LOADING_MONTH_BODY = """
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

<div class="sub-tabs">
  <a class="sub-tab {% if loading_mode == 'today' %}is-active{% endif %}" href="{{ url_for('index', tab='loading', loading_view='today', archive_date=archive_date) }}">Погрузка сегодня</a>
  <a class="sub-tab {% if loading_mode == 'yesterday' %}is-active{% endif %}" href="{{ url_for('index', tab='loading', loading_view='yesterday', archive_date=archive_date) }}">Погрузка вчера</a>
  <a class="sub-tab {% if loading_mode == 'pending' %}is-active{% endif %}" href="{{ url_for('index', tab='loading', loading_view='pending', archive_date=archive_date) }}">Погружены, но не отправлены более суток</a>
  <a class="sub-tab {% if loading_mode == 'month' %}is-active{% endif %}" href="{{ url_for('index', tab='loading', loading_view='month', loading_month=selected_month, selected_cargo=report.selected_cargo) }}">Погрузка с начала месяца</a>
</div>

<section class="card topbar">
  <div class="topbar-left">
    <div class="title">{{ app_title }} — Погрузка с начала месяца</div>
    <div class="meta">
      {{ source_name }}
      {% if source_time %} • {{ source_time }}{% endif %}
      {% if report_date_label %} • Дата справки: {{ report_date_label }}{% endif %}
      • Месяц: {{ report.month_label }}
    </div>
  </div>
  <div class="topbar-right">
    <form class="upload-form" method="post" action="{{ url_for('upload_file') }}" enctype="multipart/form-data">
      <input type="hidden" name="tab" value="loading">
      <input type="hidden" name="loading_view" value="month">
      <input type="hidden" name="loading_month" value="{{ selected_month }}">
      <input type="hidden" name="selected_cargo" value="{{ report.selected_cargo }}">
      <label class="file-label">
        <span>Выбрать Excel</span>
        <input type="file" name="excel_file" accept=".xlsx,.xls,.xlsm,.xltx,.xltm" required>
      </label>
      <button class="btn btn-primary" type="submit">Загрузить</button>
    </form>
    <form class="archive-form" method="get" action="{{ url_for('index') }}">
      <input type="hidden" name="tab" value="loading">
      <input type="hidden" name="loading_view" value="month">
      <input type="hidden" name="selected_cargo" value="{{ report.selected_cargo }}">
      <input class="archive-date" type="month" name="loading_month" value="{{ selected_month }}">
      <button class="btn btn-soft" type="submit">Открыть месяц</button>
    </form>
    <a class="btn btn-secondary" href="{{ url_for('refresh', tab='loading', loading_view='month', loading_month=selected_month, selected_cargo=report.selected_cargo) }}">Обновить</a>
  </div>
</section>

{% if success_message %}<div class="success card">{{ success_message }}</div>{% endif %}
{% if error_message %}<div class="error card">{{ error_message }}</div>{% endif %}
{% if info_message %}<div class="success card">{{ info_message }}</div>{% endif %}

<div class="header-grid header-grid-departure">
  <section class="card metric">
    <div class="label">Общий объем</div>
    <div class="value">{{ report.total_tons_label }} т</div>
    <div class="sub">Без контейнеров спец. порожних</div>
  </section>
  <section class="card metric">
    <div class="label">Погружено вагонов</div>
    <div class="value">{{ report.total_wagon_count }}</div>
    <div class="sub">Без контейнеров спец. порожних</div>
  </section>
  <section class="card metric">
    <div class="label">Наименований грузов</div>
    <div class="value">{{ report.cargo_count }}</div>
    <div class="sub">Уникальных групп</div>
  </section>
  <section class="card metric">
    <div class="label">Дней погрузки</div>
    <div class="value">{{ report.day_count }}</div>
    <div class="sub">Дней с архивными данными</div>
  </section>
  <section class="card metric">
    <div class="label">Станций назначения</div>
    <div class="value">{{ report.destination_count }}</div>
    <div class="sub">Уникальных станций</div>
  </section>
  <section class="card metric">
    <div class="label">Архивных дней</div>
    <div class="value">{{ report.covered_days }}</div>
    <div class="sub">Использовано для расчёта</div>
  </section>
  <section class="card metric">
    <div class="label">Контейнеры спец. порожние</div>
    <div class="value">{{ report.special_tons_label }} т</div>
    <div class="sub">Вагонов: {{ report.special_wagon_count }}</div>
  </section>
</div>

<section class="card table-card">
  <div class="toolbar">
    <div>
      <div class="toolbar-title">Погрузка с начала месяца</div>
      <div class="toolbar-sub">Выберите наименование груза, затем отобразится раскладка по датам и станциям назначения.</div>
    </div>
    <div class="toolbar-right">
      <form class="archive-form" method="get" action="{{ url_for('index') }}">
        <input type="hidden" name="tab" value="loading">
        <input type="hidden" name="loading_view" value="month">
        <input type="hidden" name="loading_month" value="{{ selected_month }}">
        <select class="archive-date" name="selected_cargo" style="min-width:420px;">
          {% for cargo_name in report.cargo_options %}
          <option value="{{ cargo_name }}" {% if cargo_name == report.selected_cargo %}selected{% endif %}>{{ cargo_name }}</option>
          {% endfor %}
        </select>
        <button class="btn btn-soft" type="submit">Открыть груз</button>
      </form>
    </div>
  </div>
  {% if report.selected_cargo_group %}
  <div class="toolbar" style="border-top:1px solid var(--line-soft);">
    <div>
      <div class="toolbar-title">{{ report.selected_cargo_group.cargo_name }}</div>
      <div class="toolbar-sub">Итого: {{ report.selected_cargo_group.total_tons_label }} т • Вагонов: {{ report.selected_cargo_group.wagon_count }}</div>
    </div>
  </div>
  <div class="table-wrap" style="max-height: calc(100vh - 280px);">
    <table class="summary-table" id="loading-month-detail-table">
      <thead>
        <tr>
          <th style="width:20%;" data-col-index="0"><div class="th-wrap"><span>Дата</span><button type="button" class="col-filter-btn" data-col-index="0">▾</button></div></th>
          <th style="width:32%;" data-col-index="1"><div class="th-wrap"><span>Станция назначения</span><button type="button" class="col-filter-btn" data-col-index="1">▾</button></div></th>
          <th style="width:16%;" data-col-index="2"><div class="th-wrap"><span>Вагонов</span><button type="button" class="col-filter-btn" data-col-index="2">▾</button></div></th>
          <th style="width:20%;" data-col-index="3"><div class="th-wrap"><span>Род вагона</span><button type="button" class="col-filter-btn" data-col-index="3">▾</button></div></th>
          <th style="width:12%;" data-col-index="4"><div class="th-wrap"><span>Тонн</span><button type="button" class="col-filter-btn" data-col-index="4">▾</button></div></th>
        </tr>
      </thead>
      <tbody>
        {% for item in report.selected_cargo_group.details %}
        <tr data-loading-month-row="1">
          <td data-sort-value="{{ item.date.isoformat() if item.date else '' }}">{{ item.date_label }}</td>
          <td>{{ item.destination }}</td>
          <td class="num" data-sort-value="{{ item.wagon_count }}">{{ item.wagon_count }}</td>
          <td>{{ item.wagon_kind }}</td>
          <td class="num" data-sort-value="{{ '%.3f'|format(item.tons) }}">{{ item.tons_label }} т</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  <script>
  (function(){
    const table = document.getElementById('loading-month-detail-table');
    if (!table) return;
    const rows = Array.from(table.querySelectorAll('tbody tr[data-loading-month-row="1"]'));
    const buttons = Array.from(table.querySelectorAll('.col-filter-btn'));
    const active = {};
    let popover = null;

    function getCellText(row, colIndex) {
      const cell = row.children[colIndex];
      return cell ? cell.textContent.replace(/\\s+/g, ' ').trim() : '';
    }

    function getSortValue(row, colIndex) {
      const cell = row.children[colIndex];
      if (!cell) return '';
      const raw = cell.getAttribute('data-sort-value');
      return raw !== null ? raw : getCellText(row, colIndex);
    }

    function compareValues(a, b) {
      const numA = Number(a);
      const numB = Number(b);
      if (!Number.isNaN(numA) && !Number.isNaN(numB) && String(a).trim() !== '' && String(b).trim() !== '') {
        return numA - numB;
      }
      return String(a).localeCompare(String(b), 'ru');
    }

    function rowMatches(row, excludeKey) {
      for (const key in active) {
        if (excludeKey !== undefined && String(key) === String(excludeKey)) continue;
        const state = active[key];
        if (!state || !state.values) continue;
        const text = getCellText(row, Number(key));
        if (state.values.size === 0 || !state.values.has(text)) return false;
      }
      return true;
    }

    function availableValues(colIndex) {
      const values = new Set();
      const key = String(colIndex);
      rows.forEach(function(row){ if (rowMatches(row, key)) values.add(getCellText(row, colIndex)); });
      return Array.from(values).sort(compareValues);
    }

    function applyFilters() {
      rows.forEach(function(row){
        row.style.display = rowMatches(row) ? '' : 'none';
      });
      buttons.forEach(function(btn){
        const idx = btn.getAttribute('data-col-index');
        btn.classList.toggle('is-active', !!active[idx]);
      });
    }

    function sortRows(colIndex, direction) {
      const tbody = table.tBodies[0];
      const sorted = rows.slice().sort(function(left, right){
        const result = compareValues(getSortValue(left, colIndex), getSortValue(right, colIndex));
        return direction === 'desc' ? -result : result;
      });
      sorted.forEach(function(row){ tbody.appendChild(row); });
      closePopover();
    }

    function closePopover() {
      if (popover) {
        popover.remove();
        popover = null;
      }
    }

    function renderFilterList(listNode, colIndex, values, selected, searchText) {
      listNode.innerHTML = '';
      const filteredValues = values.filter(function(value){
        return !searchText || value.toLocaleLowerCase('ru').includes(searchText);
      });
      if (!filteredValues.length) {
        const empty = document.createElement('div');
        empty.className = 'filter-empty';
        empty.textContent = 'Нет значений';
        listNode.appendChild(empty);
        return;
      }
      filteredValues.forEach(function(value){
        const label = document.createElement('label');
        label.className = 'filter-item';
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.value = value;
        checkbox.checked = selected.has(value);
        checkbox.addEventListener('change', function(){
          if (checkbox.checked) selected.add(value); else selected.delete(value);
          active[String(colIndex)] = { values: new Set(selected) };
          applyFilters();
        });
        const text = document.createElement('span');
        text.textContent = value || 'Пусто';
        label.appendChild(checkbox);
        label.appendChild(text);
        listNode.appendChild(label);
      });
    }

    function openPopover(button, colIndex) {
      closePopover();
      const key = String(colIndex);
      const values = availableValues(colIndex);
      const selected = active[key] && active[key].values ? new Set(Array.from(active[key].values).filter(function(value){ return values.includes(value); })) : new Set(values);
      popover = document.createElement('div');
      popover.className = 'filter-popover';

      const search = document.createElement('input');
      search.type = 'search';
      search.placeholder = 'Поиск';
      search.style.width = '100%';
      search.style.minHeight = '32px';
      search.style.marginBottom = '10px';
      search.style.border = '1px solid var(--line)';
      search.style.borderRadius = '8px';
      search.style.padding = '0 10px';
      popover.appendChild(search);

      const sortActions = document.createElement('div');
      sortActions.className = 'filter-actions';
      const btnSortAsc = document.createElement('button');
      btnSortAsc.type = 'button';
      btnSortAsc.textContent = 'Сортировать А→Я';
      btnSortAsc.addEventListener('click', function(){ sortRows(colIndex, 'asc'); });
      const btnSortDesc = document.createElement('button');
      btnSortDesc.type = 'button';
      btnSortDesc.textContent = 'Сортировать Я→А';
      btnSortDesc.addEventListener('click', function(){ sortRows(colIndex, 'desc'); });
      sortActions.appendChild(btnSortAsc);
      sortActions.appendChild(btnSortDesc);
      popover.appendChild(sortActions);

      const actions = document.createElement('div');
      actions.className = 'filter-actions';
      const btnAll = document.createElement('button');
      btnAll.type = 'button';
      btnAll.textContent = 'Выбрать все';
      btnAll.addEventListener('click', function(){ delete active[key]; applyFilters(); closePopover(); });
      const btnNone = document.createElement('button');
      btnNone.type = 'button';
      btnNone.textContent = 'Снять все';
      btnNone.addEventListener('click', function(){ active[key] = { values: new Set() }; applyFilters(); closePopover(); });
      const btnClear = document.createElement('button');
      btnClear.type = 'button';
      btnClear.textContent = 'Сбросить';
      btnClear.addEventListener('click', function(){ delete active[key]; applyFilters(); closePopover(); });
      actions.appendChild(btnAll);
      actions.appendChild(btnNone);
      actions.appendChild(btnClear);
      popover.appendChild(actions);

      const list = document.createElement('div');
      list.className = 'filter-list';
      popover.appendChild(list);
      document.body.appendChild(popover);
      renderFilterList(list, colIndex, values, selected, '');

      search.addEventListener('input', function(){
        renderFilterList(list, colIndex, values, selected, search.value.toLocaleLowerCase('ru').trim());
      });

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

    buttons.forEach(function(button){
      button.addEventListener('click', function(event){
        event.stopPropagation();
        openPopover(button, Number(button.getAttribute('data-col-index')));
      });
    });
    document.addEventListener('click', function(event){
      if (!popover) return;
      if (popover.contains(event.target)) return;
      if (event.target.closest('.col-filter-btn')) return;
      closePopover();
    });
    applyFilters();
  })();
  </script>
  {% elif report.cargo_options %}
    <div class="empty">Выберите наименование груза из списка.</div>
  {% else %}
    <div class="empty">За выбранный месяц по архивным справкам данные не найдены.</div>
  {% endif %}
</section>
"""
