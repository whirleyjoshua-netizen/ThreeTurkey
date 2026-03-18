/* ── Nav button → focus email input ── */
document.querySelectorAll('a[href="#checkout"]').forEach(a => {
    a.addEventListener('click', (e) => {
        e.preventDefault();
        const input = document.querySelector('#checkout-form input[name="email"]');
        if (input) { input.scrollIntoView({ behavior: 'smooth', block: 'center' }); setTimeout(() => input.focus(), 400); }
    });
});

/* ── Checkout Form Handling ── */
document.querySelectorAll('#checkout-form, #checkout-form-bottom').forEach(form => {
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const input = form.querySelector('input[name="email"]');
        const btn = form.querySelector('button');
        const email = input.value.trim();
        if (!email || !input.checkValidity()) { input.reportValidity(); return; }

        btn.disabled = true;
        btn.textContent = 'Redirecting to checkout...';

        try {
            const res = await fetch('/api/checkout', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email }),
            });
            const data = await res.json();
            if (res.ok && data.url) {
                window.location.href = data.url;
            } else {
                btn.textContent = data.detail || 'Something went wrong';
                setTimeout(() => { btn.textContent = 'Lock In Lifetime Access \u2014 $149'; btn.disabled = false; }, 3000);
            }
        } catch {
            btn.textContent = 'Error \u2014 try again';
            setTimeout(() => { btn.textContent = 'Lock In Lifetime Access \u2014 $149'; btn.disabled = false; }, 3000);
        }
    });
});

/* ── Spots Counter ── */
async function loadSpots() {
    try {
        const res = await fetch('/api/checkout/spots');
        const { paid, remaining } = await res.json();
        const el = document.getElementById('spots-paid');
        if (el && paid > 0) el.textContent = paid.toLocaleString() + ' founding members joined. ';
        const spots = document.getElementById('spots-remaining');
        if (spots) spots.textContent = remaining + ' of 500 spots remaining';
    } catch { /* silent */ }
}
loadSpots();

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
