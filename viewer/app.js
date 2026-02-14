(() => {
    let memories = [];
    let indexContent = '';
    let configContent = '';
    let currentView = 'index';

    // ── Markdown parser ──

    function md(text) {
        if (!text) return '';
        let html = text;

        // Code blocks
        html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
            const escaped = code.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
            return `<pre><code>${escaped.trimEnd()}</code></pre>`;
        });

        const lines = html.split('\n');
        const result = [];
        let inList = false;
        let listType = null;
        let inTable = false;
        let tableRows = [];

        function flushTable() {
            if (!inTable || tableRows.length === 0) return;
            let t = '<table><thead><tr>';
            const headers = tableRows[0];
            headers.forEach(h => t += `<th>${processInline(h.trim())}</th>`);
            t += '</tr></thead><tbody>';
            for (let i = 2; i < tableRows.length; i++) {
                t += '<tr>';
                tableRows[i].forEach(c => t += `<td>${processInline(c.trim())}</td>`);
                t += '</tr>';
            }
            t += '</tbody></table>';
            result.push(t);
            tableRows = [];
            inTable = false;
        }

        function flushList() {
            if (inList) {
                result.push(listType === 'ol' ? '</ol>' : '</ul>');
                inList = false;
                listType = null;
            }
        }

        for (const line of lines) {
            if (line.startsWith('<pre>') || line.startsWith('</pre>')) {
                flushList(); flushTable();
                result.push(line);
                continue;
            }

            if (line.trim().startsWith('|') && line.trim().endsWith('|')) {
                flushList();
                const cells = line.trim().slice(1, -1).split('|');
                if (cells.every(c => /^[\s-:]+$/.test(c))) {
                    tableRows.push(cells);
                    inTable = true;
                    continue;
                }
                tableRows.push(cells);
                inTable = true;
                continue;
            } else if (inTable) {
                flushTable();
            }

            if (line.startsWith('### ')) {
                flushList();
                result.push(`<h3>${processInline(line.slice(4))}</h3>`);
            } else if (line.startsWith('## ')) {
                flushList();
                result.push(`<h2>${processInline(line.slice(3))}</h2>`);
            } else if (line.startsWith('# ')) {
                flushList();
                result.push(`<h1>${processInline(line.slice(2))}</h1>`);
            } else if (/^[-*]\s/.test(line.trim())) {
                if (!inList || listType !== 'ul') {
                    flushList();
                    result.push('<ul>');
                    inList = true;
                    listType = 'ul';
                }
                result.push(`<li>${processInline(line.trim().slice(2))}</li>`);
            } else if (/^\d+\.\s/.test(line.trim())) {
                if (!inList || listType !== 'ol') {
                    flushList();
                    result.push('<ol>');
                    inList = true;
                    listType = 'ol';
                }
                result.push(`<li>${processInline(line.trim().replace(/^\d+\.\s/, ''))}</li>`);
            } else if (/^---+$/.test(line.trim())) {
                flushList();
                result.push('<hr>');
            } else if (line.trim() === '') {
                flushList();
            } else {
                flushList();
                result.push(`<p>${processInline(line)}</p>`);
            }
        }
        flushList();
        flushTable();
        return result.join('\n');
    }

    function processInline(text) {
        return text
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            .replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
            .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.+?)\*/g, '<em>$1</em>')
            .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>');
    }

    // ── Dates ──

    function formatDate(dateStr) {
        const d = new Date(dateStr + 'T12:00:00');
        const weekday = d.toLocaleDateString('en-US', { weekday: 'long' });
        const month = d.toLocaleDateString('en-US', { month: 'long' });
        const day = d.getDate();
        const year = d.getFullYear();
        return { full: `${month} ${day}, ${year}`, weekday };
    }

    // ── Stats ──

    function computeStats() {
        const totalDays = memories.length;
        const totalSections = memories.reduce((sum, m) => sum + m.sections.length, 0);
        const totalWords = memories.reduce((sum, m) =>
            sum + m.sections.reduce((s, sec) => s + sec.content.split(/\s+/).filter(w => w).length, 0), 0);
        const firstDate = memories.length ? memories[memories.length - 1].date : null;
        const lastDate = memories.length ? memories[0].date : null;

        // Top topics from section titles
        const titleCounts = {};
        for (const m of memories) {
            for (const s of m.sections) {
                const title = s.title.trim();
                titleCounts[title] = (titleCounts[title] || 0) + 1;
            }
        }
        const topTopics = Object.entries(titleCounts)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 5)
            .map(([title, count]) => ({ title, count }));

        return { totalDays, totalSections, totalWords, firstDate, lastDate, topTopics };
    }

    function renderStats() {
        const stats = computeStats();
        const el = document.getElementById('stats');
        if (!stats.firstDate) {
            el.innerHTML = '';
            return;
        }

        const { full: firstFull } = formatDate(stats.firstDate);
        const wordStr = stats.totalWords.toLocaleString();

        let html = '<div class="stats-bar">';
        html += '<span class="stats-sys-label">SYS.STATUS</span>';
        html += `<span class="stat"><span class="stat-label">DAYS</span> <span class="stat-value">${stats.totalDays}</span></span>`;
        html += `<span class="stat-sep"></span>`;
        html += `<span class="stat"><span class="stat-label">SECTIONS</span> <span class="stat-value">${stats.totalSections}</span></span>`;
        html += `<span class="stat-sep"></span>`;
        html += `<span class="stat"><span class="stat-label">WORDS</span> <span class="stat-value">${wordStr}</span></span>`;
        html += `<span class="stat-sep"></span>`;
        html += `<span class="stat"><span class="stat-label">ORIGIN</span> <span class="stat-value">${firstFull}</span></span>`;
        html += '</div>';

        if (stats.topTopics.length > 0) {
            html += '<div class="stats-topics">';
            for (const t of stats.topTopics) {
                html += `<span class="topic-tag">${t.title}<span class="topic-count">${t.count}</span></span>`;
            }
            html += '</div>';
        }

        el.innerHTML = html;
    }

    // ── Calendar ──

    function renderCalendar(memoryDates) {
        const cal = document.getElementById('calendar');
        const dateSet = new Set(memoryDates);
        const today = new Date();
        today.setHours(12, 0, 0, 0);

        // Dynamic range: from earliest entry to today (minimum 30 days)
        let startDate = new Date(today);
        startDate.setDate(startDate.getDate() - 29);
        if (memoryDates.length > 0) {
            const sorted = [...memoryDates].sort();
            const earliest = new Date(sorted[0] + 'T12:00:00');
            if (earliest < startDate) startDate = earliest;
        }

        const dayCount = Math.round((today - startDate) / (1000 * 60 * 60 * 24)) + 1;
        const days = [];
        for (let i = dayCount - 1; i >= 0; i--) {
            const d = new Date(today);
            d.setDate(d.getDate() - i);
            days.push(d);
        }

        const label = dayCount <= 30 ? 'This month' : `${dayCount} days of memory`;
        let html = `<div class="cal-label">${label}</div><div class="calendar-strip">`;
        for (const d of days) {
            const iso = d.toISOString().split('T')[0];
            const isToday = iso === today.toISOString().split('T')[0];
            const hasEntry = dateSet.has(iso);
            const label = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
            const classes = ['cal-day'];
            if (hasEntry) classes.push('has-entry');
            if (isToday) classes.push('today');
            html += `<div class="${classes.join(' ')}" data-date="${iso}">`;
            html += `<div class="cal-tooltip">${label}${hasEntry ? ' \u2014 entry' : ''}</div>`;
            html += '</div>';
        }
        html += '</div>';
        cal.innerHTML = html;

        cal.querySelectorAll('.cal-day.has-entry').forEach(el => {
            el.addEventListener('click', () => {
                const needsSwitch = currentView !== 'timeline';
                if (needsSwitch) switchView('timeline');
                setTimeout(() => {
                    const card = document.querySelector(`[data-day="${el.dataset.date}"]`);
                    if (card) {
                        card.classList.add('open');
                        card.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    }
                }, needsSwitch ? 250 : 50);
            });
        });
    }

    // ── Index view ──

    function renderIndex(filter = '') {
        const el = document.getElementById('content');
        let rendered = md(indexContent);
        if (filter) {
            rendered = highlightMatches(rendered, filter);
        }
        el.innerHTML = `<div class="index-content">${rendered}</div>`;
        animate(el);
    }

    // ── Timeline view ──

    function renderTimeline(filter = '') {
        const el = document.getElementById('content');
        const lowerFilter = filter.toLowerCase();

        let filtered = memories;
        if (lowerFilter) {
            filtered = memories.filter(m =>
                m.sections.some(s =>
                    s.title.toLowerCase().includes(lowerFilter) ||
                    s.content.toLowerCase().includes(lowerFilter)
                )
            );
        }

        if (filtered.length === 0) {
            el.innerHTML = `
                <div class="empty-state">
                    <p>No memories match \u201c${filter}\u201d</p>
                </div>`;
            return;
        }

        let info = '';
        if (lowerFilter) {
            const totalSections = filtered.reduce((sum, m) =>
                sum + m.sections.filter(s =>
                    s.title.toLowerCase().includes(lowerFilter) ||
                    s.content.toLowerCase().includes(lowerFilter)
                ).length, 0);
            info = `<div class="search-info"><strong>${totalSections}</strong> matching section${totalSections !== 1 ? 's' : ''} across <strong>${filtered.length}</strong> day${filtered.length !== 1 ? 's' : ''}</div>`;
        }

        let html = info + '<div class="timeline">';
        for (const m of filtered) {
            const { full, weekday } = formatDate(m.date);
            const sections = lowerFilter
                ? m.sections.filter(s =>
                    s.title.toLowerCase().includes(lowerFilter) ||
                    s.content.toLowerCase().includes(lowerFilter))
                : m.sections;

            const badges = sections.slice(0, 3).map(s =>
                `<span class="badge">${s.title}</span>`
            ).join('');
            const extra = sections.length > 3 ? `<span class="badge">+${sections.length - 3}</span>` : '';

            html += `<div class="day-entry${lowerFilter ? ' open' : ''}" data-day="${m.date}">`;
            html += `<div class="day-header">`;
            html += `<div><span class="day-date">${full}<span class="day-weekday">${weekday}</span></span></div>`;
            html += `<div style="display:flex;align-items:center;gap:10px">`;
            html += `<div class="day-badges">${badges}${extra}</div>`;
            html += `<svg class="day-expand" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="6 9 12 15 18 9"/></svg>`;
            html += `</div></div>`;
            html += `<div class="day-sections">`;
            for (const s of sections) {
                let rendered = md(s.content);
                if (lowerFilter) rendered = highlightMatches(rendered, lowerFilter);
                html += `<div class="section">`;
                html += `<div class="section-title">${lowerFilter ? highlightMatches(s.title, lowerFilter) : s.title}</div>`;
                html += `<div class="section-body">${rendered}</div>`;
                html += `</div>`;
            }
            html += `</div></div>`;
        }
        html += '</div>';
        el.innerHTML = html;

        // Toggle entries
        el.querySelectorAll('.day-header').forEach(header => {
            header.addEventListener('click', () => {
                header.closest('.day-entry').classList.toggle('open');
            });
        });

        animate(el);
    }

    function highlightMatches(html, query) {
        const parts = html.split(/(<[^>]+>)/);
        return parts.map(part => {
            if (part.startsWith('<')) return part;
            const regex = new RegExp(`(${escapeRegex(query)})`, 'gi');
            return part.replace(regex, '<mark>$1</mark>');
        }).join('');
    }

    function escapeRegex(str) {
        return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    // ── Config view ──

    function renderConfig(filter = '') {
        const el = document.getElementById('content');
        let rendered = md(configContent);
        if (filter) {
            rendered = highlightMatches(rendered, filter);
        }
        el.innerHTML = `<div class="index-content">${rendered}</div>`;
        animate(el);
    }

    // ── View switching ──

    function switchView(view) {
        currentView = view;
        document.getElementById('view-index').classList.toggle('active', view === 'index');
        document.getElementById('view-timeline').classList.toggle('active', view === 'timeline');
        document.getElementById('view-config').classList.toggle('active', view === 'config');

        const content = document.getElementById('content');
        content.style.opacity = '0';
        content.style.transform = 'translateY(8px)';

        const query = document.getElementById('search').value.trim();
        setTimeout(() => {
            if (view === 'index') {
                renderIndex(query);
            } else if (view === 'config') {
                renderConfig(query);
            } else {
                renderTimeline(query);
            }
            content.style.opacity = '1';
            content.style.transform = 'translateY(0)';
        }, 150);
    }

    function animate(el) {
        el.style.opacity = '0';
        el.style.transform = 'translateY(8px)';
        requestAnimationFrame(() => {
            el.style.transition = 'opacity 0.35s ease, transform 0.35s ease';
            el.style.opacity = '1';
            el.style.transform = 'translateY(0)';
        });
    }

    // ── Ambient ──

    function startAmbient() {
        // Live clock
        const clockEl = document.getElementById('clock');
        if (clockEl) {
            const tick = () => {
                const n = new Date();
                clockEl.textContent =
                    String(n.getHours()).padStart(2, '0') + ':' +
                    String(n.getMinutes()).padStart(2, '0') + ':' +
                    String(n.getSeconds()).padStart(2, '0');
            };
            tick();
            setInterval(tick, 1000);
        }

        // Data stream — scrolling hex
        const streamEl = document.getElementById('dataStream');
        if (streamEl) {
            let t = '';
            for (let i = 0; i < 400; i++) {
                const r = Math.random();
                if (r < 0.7) {
                    t += Math.floor(Math.random() * 256).toString(16).toUpperCase().padStart(2, '0');
                } else {
                    t += ' ';
                }
            }
            const inner = document.createElement('div');
            inner.className = 'stream-inner';
            inner.textContent = t + t;
            streamEl.appendChild(inner);
        }
    }

    // ── Init ──

    async function init() {
        const [memRes, idxRes, cfgRes] = await Promise.all([
            fetch('/api/memories'),
            fetch('/api/index'),
            fetch('/api/config'),
        ]);
        memories = await memRes.json();
        const idx = await idxRes.json();
        indexContent = idx.content;
        const cfg = await cfgRes.json();
        configContent = cfg.content;

        renderStats();
        renderCalendar(memories.map(m => m.date));
        renderIndex();
        startAmbient();

        document.getElementById('view-index').addEventListener('click', () => switchView('index'));
        document.getElementById('view-timeline').addEventListener('click', () => switchView('timeline'));
        document.getElementById('view-config').addEventListener('click', () => switchView('config'));

        const searchInput = document.getElementById('search');
        let debounce;
        searchInput.addEventListener('input', () => {
            clearTimeout(debounce);
            debounce = setTimeout(() => {
                const q = searchInput.value.trim();
                if (currentView === 'index') {
                    renderIndex(q);
                } else if (currentView === 'config') {
                    renderConfig(q);
                } else {
                    renderTimeline(q);
                }
            }, 200);
        });

        document.addEventListener('keydown', e => {
            if (e.key === '/' && document.activeElement !== searchInput) {
                e.preventDefault();
                searchInput.focus();
            }
            if (e.key === 'Escape' && document.activeElement === searchInput) {
                searchInput.blur();
                searchInput.value = '';
                if (currentView === 'index') renderIndex('');
                else if (currentView === 'config') renderConfig('');
                else renderTimeline('');
            }
        });
    }

    init();
})();
