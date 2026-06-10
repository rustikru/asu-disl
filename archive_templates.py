from __future__ import annotations

ARCHIVE_BODY = """
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
    <div class="title">{{ app_title }} — Архив</div>
    <div class="meta">Поиск вагонов по архивным справкам по номерам, периоду и при необходимости по станции операции</div>
  </div>
</section>

{% if success_message %}<div class="success card">{{ success_message }}</div>{% endif %}
{% if error_message %}<div class="error card">{{ error_message }}</div>{% endif %}

<section class="card table-card" style="padding:12px; margin-bottom:12px;">
  <div class="toolbar" style="margin:-12px -12px 12px -12px;">
    <div>
      <div class="toolbar-title">Фильтр поиска</div>
      <div class="toolbar-sub">Станция проверяется по колонке «Станция операции» (AF). Поле станции можно не заполнять.</div>
    </div>
  </div>
  <form method="get" action="{{ url_for('archive_search') }}" class="form-row">
    <textarea class="input archive-wagon-input" name="wagon" placeholder="Номер или список вагонов" style="min-width:220px; min-height:42px; resize:vertical;" required>{{ wagon }}</textarea>
    <input class="input" type="text" name="station" value="{{ station }}" placeholder="Станция операции (необязательно)" list="archive-station-list" style="min-width:260px;">
    <datalist id="archive-station-list">
      {% for option in station_options %}
      <option value="{{ option }}"></option>
      {% endfor %}
    </datalist>
    <label class="mini-muted">С:
      <input class="input" type="date" name="date_from" value="{{ date_from }}" required>
    </label>
    <label class="mini-muted">По:
      <input class="input" type="date" name="date_to" value="{{ date_to }}" required>
    </label>
    <button class="btn btn-primary" type="submit">Найти</button>
    <a class="btn btn-secondary" href="{{ url_for('archive_search') }}">Сбросить</a>
  </form>
</section>

<div class="header-grid header-grid-approach">
  <section class="card metric">
    <div class="label">Найдено записей</div>
    <div class="value">{{ total_count }}</div>
    <div class="sub">За выбранный период</div>
  </section>
  <section class="card metric">
    <div class="label">Вагоны</div>
    <div class="value">{{ requested_count or "—" }}</div>
    <div class="sub">{% if archive_summary %}{{ archive_summary }}{% else %}Фильтр поиска{% endif %}</div>
  </section>
  <section class="card metric">
    <div class="label">Станция операции</div>
    <div class="value">{{ station or "—" }}</div>
    <div class="sub">AF / все станции, если пусто</div>
  </section>
</div>

{% if archive_summary %}
<section class="card table-card" style="padding:12px; margin-bottom:12px;">
  <div class="toolbar-title">Результат поиска по вагонам</div>
  <div class="toolbar-sub">{{ archive_summary }}</div>
  {% if not_found_wagons %}
  <div class="toolbar-sub" style="margin-top:6px;">Не найдено {{ not_found_wagons|length }} вагонов: {{ not_found_wagons|join(', ') }}</div>
  {% endif %}
</section>
{% endif %}

<section class="card table-card">
  <div class="toolbar">
    <div>
      <div class="toolbar-title">Результаты поиска</div>
      <div class="toolbar-sub">{{ filter_caption }}</div>
    </div>
    <div class="toolbar-right">
      {% if records and export_link %}<a class="btn btn-soft" href="{{ export_link }}">Excel</a>{% endif %}
      <span class="badge">Показано: {{ total_count }}</span>
    </div>
  </div>
  {% if records %}
  <div class="table-wrap">
    <table class="detail-table">
      <thead>
        <tr>
          <th class="detail-col-date">Дата архива</th>
          <th class="detail-col-wagon">№ ваг.</th>
          <th class="detail-col-kind">Род ваг.</th>
          <th class="detail-col-date">Нач. рейса</th>
          <th class="detail-col-date">Дата и время окончания рейса</th>
          <th class="detail-col-road">Дор. отпр.</th>
          <th class="detail-col-station">Ст. отпр.</th>
          <th class="detail-col-road">Дор. назн.</th>
          <th class="detail-col-dest">Ст. назн.</th>
          <th class="detail-col-owner">Грузоотпр.</th>
          <th class="detail-col-cargo">Груз</th>
          <th class="detail-col-cargo">Ранее выгруженный груз</th>
          <th class="detail-col-weight">Вес, кг</th>
          <th class="detail-col-station">Ст. опер.</th>
          <th class="detail-col-road">Дор. опер.</th>
          <th class="detail-col-op">Опер.</th>
          <th class="detail-col-date">Дата/время опер.</th>
          <th class="detail-col-train">Индекс поезда</th>
          <th class="detail-col-cargo">Контейнеры</th>
          <th class="detail-col-date">Норм. срок</th>
          <th class="detail-col-dist">Пройд., км</th>
          <th class="detail-col-dist">Ост., км</th>
          <th class="detail-col-date">Простой, сут.</th>
          <th class="detail-col-date">Отпр. со ст. пр.</th>
          <th class="detail-col-arrival">Приб. на ст. назн.</th>
          <th class="detail-col-state">Сост. ваг.</th>
          <th class="detail-col-owner">Собств.</th>
        </tr>
      </thead>
      <tbody>
        {% for item in records %}
        <tr data-detail-row="1">
          <td>{{ item.archive_date_label }}</td>
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
  {% else %}
    <div class="empty">{{ empty_message }}</div>
  {% endif %}
</section>

<script>
(function(){
  var rows=document.querySelectorAll('.detail-table tbody tr');
  if(!rows.length){return;}
  rows.forEach(function(row){
    row.addEventListener('click', function(event){
      var target=event.target;
      if(target && target.closest('a, button, input, select, textarea, label')){return;}
      rows.forEach(function(item){ if(item!==row){ item.classList.remove('asu-selected-row'); } });
      row.classList.toggle('asu-selected-row');
    });
  });
})();
</script>
"""
