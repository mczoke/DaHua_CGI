/* DaHua_CGI Web UI — Shared JavaScript utilities */

function showToast(msg, type = 'info') {
    const container = document.getElementById('toastContainer') || (() => {
        const c = document.createElement('div');
        c.id = 'toastContainer';
        c.className = 'app-toast-container';
        c.setAttribute('aria-live', 'polite');
        c.setAttribute('aria-atomic', 'true');
        document.body.appendChild(c);
        return c;
    })();
    const t = document.createElement('div');
    t.className = `toast align-items-center text-bg-${type} border-0 show`;
    t.innerHTML = `<div class="d-flex"><div class="toast-body">${escapeHtml(msg)}</div><button type="button" class="btn-close me-2 m-auto" data-bs-dismiss="toast" aria-label="关闭"></button></div>`;
    container.appendChild(t);
    setTimeout(() => t.remove(), 4000);
}

function escapeHtml(s) {
    if (s === null || s === undefined) return '';
    const d = document.createElement('div');
    d.textContent = String(s);
    return d.innerHTML;
}

function formatTime(seconds) {
    if (!seconds && seconds !== 0) return '--';
    return seconds.toFixed(1);
}
