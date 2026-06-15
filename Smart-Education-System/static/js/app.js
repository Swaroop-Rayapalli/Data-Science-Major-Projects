/* ============================================
   EduAI Platform - Main JavaScript
   ============================================ */

// ---- Live Clock ----
function updateClock() {
    const el = document.getElementById('currentTime');
    if (!el) return;
    const now = new Date();
    el.textContent = now.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: true
    });
}
setInterval(updateClock, 1000);
updateClock();

// ---- Sidebar Toggle ----
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    sidebar.classList.toggle('open');
}

// Close sidebar on outside click (mobile)
document.addEventListener('click', function(e) {
    const sidebar = document.getElementById('sidebar');
    const toggle = document.getElementById('sidebarToggle');
    if (window.innerWidth <= 992 && sidebar && toggle) {
        if (!sidebar.contains(e.target) && !toggle.contains(e.target)) {
            sidebar.classList.remove('open');
        }
    }
});

// ---- Animate Stats on page load ----
function animateValue(el, start, end, duration) {
    if (!el) return;
    const isFloat = String(end).includes('.');
    const startTime = performance.now();
    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        const value = start + (end - start) * eased;
        el.textContent = isFloat ? value.toFixed(1) : Math.round(value);
        if (progress < 1) requestAnimationFrame(update);
    }
    requestAnimationFrame(update);
}

// Animate stat values on load
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.stat-value').forEach(el => {
        const raw = parseFloat(el.textContent.replace('%', '').trim());
        if (!isNaN(raw)) {
            el.textContent = '0';
            animateValue(el, 0, raw, 1200);
        }
    });
});

// ---- Auto-dismiss Flash Messages ----
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.custom-alert').forEach(function(alert) {
        setTimeout(function() {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            if (bsAlert) bsAlert.close();
        }, 5000);
    });
});

// ---- Tooltip Initialization ----
document.addEventListener('DOMContentLoaded', function() {
    const tooltipEls = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    tooltipEls.forEach(el => new bootstrap.Tooltip(el));
});

// ---- Chart.js Global Defaults ----
if (typeof Chart !== 'undefined') {
    Chart.defaults.color = '#94a3b8';
    Chart.defaults.font.family = 'Inter';
    Chart.defaults.animation.duration = 800;
    Chart.defaults.animation.easing = 'easeInOutQuart';
}

// ---- Smooth card hover effect ----
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.stat-card, .chart-card, .activity-card').forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.transition = 'all 0.25s cubic-bezier(0.4, 0, 0.2, 1)';
        });
    });
});

// ---- Form Input Animation ----
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.custom-input, .custom-textarea').forEach(input => {
        input.addEventListener('focus', function() {
            this.closest('.form-group')?.querySelector('.form-label-custom')?.classList.add('label-active');
        });
        input.addEventListener('blur', function() {
            this.closest('.form-group')?.querySelector('.form-label-custom')?.classList.remove('label-active');
        });
    });
});

// ---- Page load animation ----
document.addEventListener('DOMContentLoaded', function() {
    document.body.style.opacity = '0';
    document.body.style.transition = 'opacity 0.3s ease';
    requestAnimationFrame(() => {
        document.body.style.opacity = '1';
    });
});
