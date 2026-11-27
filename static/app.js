const doctors = JSON.parse(document.getElementById('doctors-data').textContent);
const list = document.getElementById('doctor-list');
const details = document.getElementById('details');
const search = document.getElementById('search');
const filter = document.getElementById('status-filter');
const empty = document.getElementById('empty');
let selected = doctors.length ? doctors[0].index : null;

const labels = {matched: 'Совпало', possible: 'Возможно совпадение', api_only: 'Только в Medical API', catalog_only: 'Только в каталоге'};
const esc = value => String(value ?? '—').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const same = (a, b) => String(a ?? '').toLowerCase().replaceAll('ё', 'е') === String(b ?? '').toLowerCase().replaceAll('ё', 'е');

function field(label, value, different = false) {
    return `<div class="field"><span class="field-label">${label}</span><span class="field-value${different ? ' diff' : ''}${value == null ? ' missing' : ''}">${esc(value ?? 'Не указано')}</span></div>`;
}

function showDetails(index) {
    const doctor = doctors.find(item => item.index === index);
    if (!doctor) { details.innerHTML = ''; return; }
    selected = index;
    document.querySelectorAll('.doctor-row').forEach(row => row.classList.toggle('selected', Number(row.dataset.index) === index));
    const api = doctor.api;
    const catalog = doctor.catalog;
    const differentName = api && catalog && !same(api.name, catalog.name);
    const differentSpecialty = api && catalog && !same(api.specialty, catalog.specialty);
    const differentExperience = api && catalog && api.experience !== catalog.experience;
    details.innerHTML = `
        <div class="detail-kicker">Карточка сравнения</div>
        <h2>${esc(doctor.name)}</h2>
        <p class="detail-specialty">${esc(doctor.specialty)}</p>
        <span class="badge ${doctor.status}">${labels[doctor.status]}</span>
        ${doctor.reason ? `<div class="reason ${doctor.status === 'possible' ? '' : 'neutral'}">${esc(doctor.reason)}</div>` : ''}
        <div class="comparison">
            <section class="source-card api"><div class="source-title">MEDICAL API</div>
                ${api ? field('ФИО', api.name, differentName) + field('Специальность', api.specialty, differentSpecialty) + field('Стаж', api.experience == null ? null : api.experience + ' лет', differentExperience) : '<p class="missing">Запись отсутствует</p>'}
            </section>
            <section class="source-card catalog"><div class="source-title">DOCTOR CATALOG</div>
                ${catalog ? field('ФИО', catalog.name, differentName) + field('Специальность', catalog.specialty, differentSpecialty) + field('Стаж', catalog.experience == null ? null : catalog.experience + ' лет', differentExperience) + field('Клиника', catalog.clinic) + field('Публичная цена', catalog.price) + (catalog.url ? `<a class="catalog-link" href="${esc(catalog.url)}" target="_blank" rel="noopener">Открыть карточку в каталоге ↗</a>` : '') : '<p class="missing">Запись отсутствует</p>'}
            </section>
        </div>
        <p class="detail-foot">Оранжевым отмечены различающиеся значения. Точный статус означает совпадение ФИО и специальности, даже если стаж различается.</p>`;
}

function applyFilters() {
    const query = search.value.trim().toLowerCase().replaceAll('ё', 'е');
    let visible = 0;
    let firstVisible = null;
    document.querySelectorAll('.doctor-row').forEach(row => {
        const show = (filter.value === 'all' || row.dataset.status === filter.value) && row.dataset.search.replaceAll('ё', 'е').includes(query);
        row.hidden = !show;
        if (show) { visible++; firstVisible ??= Number(row.dataset.index); }
    });
    empty.hidden = visible !== 0;
    list.hidden = visible === 0;
    if (!visible) details.innerHTML = '<div class="empty"><strong>Нет карточки для показа</strong><span>Сбросьте фильтры, чтобы продолжить.</span></div>';
    else if (document.querySelector(`.doctor-row[data-index="${selected}"]:not([hidden])`)) showDetails(selected);
    else showDetails(firstVisible);
}

list?.addEventListener('click', event => {
    const row = event.target.closest('.doctor-row');
    if (row) showDetails(Number(row.dataset.index));
});
search?.addEventListener('input', applyFilters);
filter?.addEventListener('change', applyFilters);
document.getElementById('reset')?.addEventListener('click', () => { search.value = ''; filter.value = 'all'; applyFilters(); });
if (doctors.length) showDetails(selected);

document.getElementById('refresh-form')?.addEventListener('submit', () => {
    document.getElementById('loading').hidden = false;
    document.getElementById('refresh-button').disabled = true;
    document.getElementById('refresh-button').innerHTML = '<span class="spinner"></span> Обновляем…';
});
