/* ── Waitlist Form Handling ── */
document.querySelectorAll('.waitlist-form').forEach(form => {
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const input = form.querySelector('input[name="email"]');
        const btn = form.querySelector('button');
        const email = input.value.trim();
        if (!email) return;

        btn.disabled = true;
        btn.textContent = 'Joining...';

        try {
            const res = await fetch('/api/waitlist', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email }),
            });
            const data = await res.json();
            if (res.ok) {
                input.value = '';
                btn.textContent = "You're In!";
                setTimeout(() => { btn.textContent = 'Join the Waitlist'; btn.disabled = false; }, 3000);
                loadCount();
            } else {
                btn.textContent = data.detail || 'Already signed up';
                setTimeout(() => { btn.textContent = 'Join the Waitlist'; btn.disabled = false; }, 2500);
            }
        } catch {
            btn.textContent = 'Error — try again';
            setTimeout(() => { btn.textContent = 'Join the Waitlist'; btn.disabled = false; }, 2500);
        }
    });
});

/* ── Waitlist Count ── */
async function loadCount() {
    try {
        const res = await fetch('/api/waitlist/count');
        const { count } = await res.json();
        const el = document.getElementById('waitlist-count');
        if (el && count > 0) el.textContent = count.toLocaleString() + ' people on the waitlist. ';
    } catch { /* silent */ }
}
loadCount();

/* ── Scroll Reveal ── */
const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.classList.add('visible');
            observer.unobserve(entry.target);
        }
    });
}, { threshold: 0.1 });

document.querySelectorAll('.section-title, .compare-card, .step, .feature-card, .price-card, .faq-item').forEach(el => {
    el.classList.add('fade-in');
    observer.observe(el);
});
