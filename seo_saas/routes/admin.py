import hashlib
import secrets
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
import seo_saas.storage.database as store
import io, csv

router = APIRouter(prefix="/admin")

ADMIN_EMAIL = "whirleyjoshua@gmail.com"
ADMIN_HASH = "5648951832a0f6f1f9617cbf7630baddde084bcc0fd34454fe9959dc0d7785f5"

# Simple in-memory session store
_sessions: set[str] = set()


def _check(password: str) -> bool:
    return hashlib.sha256(password.encode()).hexdigest() == ADMIN_HASH


def _authed(request: Request) -> bool:
    token = request.cookies.get("admin_session")
    return token in _sessions if token else False


class LoginBody(BaseModel):
    email: str
    password: str


@router.post("/login")
async def login(body: LoginBody, response: Response):
    if body.email != ADMIN_EMAIL or not _check(body.password):
        raise HTTPException(401, "Invalid credentials")
    token = secrets.token_hex(32)
    _sessions.add(token)
    response.set_cookie("admin_session", token, httponly=True, samesite="strict", max_age=86400)
    return {"ok": True}


@router.post("/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("admin_session")
    _sessions.discard(token)
    response.delete_cookie("admin_session")
    return {"ok": True}


@router.get("/emails")
async def get_emails(request: Request):
    if not _authed(request):
        raise HTTPException(401, "Not authenticated")
    if not store.db:
        return {"emails": [], "customers": []}
    async with store.db.execute("SELECT id, email, created_at FROM waitlist ORDER BY id DESC") as cursor:
        rows = await cursor.fetchall()
    async with store.db.execute("SELECT id, email, amount_paid, paid_at FROM customers ORDER BY id DESC") as cursor:
        crows = await cursor.fetchall()
    return {
        "emails": [{"id": r[0], "email": r[1], "created_at": r[2]} for r in rows],
        "customers": [{"id": r[0], "email": r[1], "amount": r[2], "paid_at": r[3]} for r in crows],
    }


@router.get("/export.csv")
async def export_csv(request: Request):
    if not _authed(request):
        raise HTTPException(401, "Not authenticated")
    if not store.db:
        rows = []
    else:
        async with store.db.execute("SELECT id, email, created_at FROM waitlist ORDER BY id DESC") as cursor:
            rows = await cursor.fetchall()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "email", "signed_up"])
    for r in rows:
        writer.writerow(r)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=waitlist.csv"},
    )


@router.get("", response_class=HTMLResponse)
async def admin_page(request: Request):
    return HTMLResponse(ADMIN_HTML)


ADMIN_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Three Turkey Admin</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0a0a0f; color: #e8e8ed; min-height: 100vh; display: flex; align-items: center; justify-content: center; }
  .card { background: #111118; border: 1px solid rgba(255,255,255,.08); border-radius: 12px; padding: 40px; width: 100%; max-width: 600px; }
  h1 { font-size: 1.5rem; margin-bottom: 24px; }
  h2 { font-size: 1.2rem; margin-bottom: 16px; }
  input { width: 100%; padding: 12px 16px; background: #1a1a24; border: 1px solid rgba(255,255,255,.1); border-radius: 8px; color: #e8e8ed; font-size: 1rem; margin-bottom: 12px; outline: none; }
  input:focus { border-color: #6c5ce7; }
  button, .btn { display: inline-block; padding: 12px 24px; background: #6c5ce7; color: #fff; border: none; border-radius: 8px; font-size: .95rem; font-weight: 600; cursor: pointer; text-decoration: none; }
  button:hover, .btn:hover { background: #5a4bd4; }
  .btn-sm { padding: 8px 16px; font-size: .85rem; }
  .btn-outline { background: transparent; border: 2px solid #6c5ce7; color: #a29bfe; }
  .error { color: #e17055; font-size: .85rem; margin-top: 8px; display: none; }
  table { width: 100%; border-collapse: collapse; margin-top: 16px; }
  th, td { text-align: left; padding: 10px 12px; border-bottom: 1px solid rgba(255,255,255,.06); font-size: .9rem; }
  th { color: #9898a6; font-weight: 600; font-size: .8rem; text-transform: uppercase; letter-spacing: .05em; }
  .actions { display: flex; gap: 12px; margin-bottom: 20px; align-items: center; }
  .count { color: #9898a6; font-size: .9rem; }
  #login-view, #dash-view { display: none; }
</style>
</head>
<body>
<div class="card">
  <!-- Login -->
  <div id="login-view">
    <h1>Three Turkey Admin</h1>
    <form id="login-form">
      <input type="email" id="l-email" placeholder="Email" required>
      <input type="password" id="l-pass" placeholder="Password" required>
      <button type="submit">Sign In</button>
      <p class="error" id="l-error"></p>
    </form>
  </div>

  <!-- Dashboard -->
  <div id="dash-view">
    <h2>Paid Customers</h2>
    <div class="actions">
      <span class="count" id="customer-total"></span>
      <button class="btn btn-sm btn-outline" onclick="doLogout()">Logout</button>
    </div>
    <table>
      <thead><tr><th>#</th><th>Email</th><th>Amount</th><th>Paid</th></tr></thead>
      <tbody id="customer-list"></tbody>
    </table>

    <h2 style="margin-top:32px;">Waitlist Signups</h2>
    <div class="actions">
      <span class="count" id="total"></span>
      <a class="btn btn-sm btn-outline" href="/admin/export.csv">Export CSV</a>
    </div>
    <table>
      <thead><tr><th>#</th><th>Email</th><th>Signed Up</th></tr></thead>
      <tbody id="email-list"></tbody>
    </table>
  </div>
</div>

<script>
const loginView = document.getElementById('login-view');
const dashView = document.getElementById('dash-view');

async function checkAuth() {
  try {
    const res = await fetch('/admin/emails');
    if (res.ok) { showDash(await res.json()); return; }
  } catch {}
  loginView.style.display = 'block';
}

function showDash(data) {
  loginView.style.display = 'none';
  dashView.style.display = 'block';
  const customers = data.customers || [];
  document.getElementById('customer-total').textContent = customers.length + ' paid customer' + (customers.length !== 1 ? 's' : '') + ' (' + (500 - customers.length) + ' spots left)';
  document.getElementById('customer-list').innerHTML = customers.map(c =>
    '<tr><td>' + c.id + '</td><td>' + c.email + '</td><td>$' + (c.amount / 100).toFixed(2) + '</td><td>' + (c.paid_at || '') + '</td></tr>'
  ).join('');
  const emails = data.emails || [];
  document.getElementById('total').textContent = emails.length + ' signup' + (emails.length !== 1 ? 's' : '');
  document.getElementById('email-list').innerHTML = emails.map(e =>
    '<tr><td>' + e.id + '</td><td>' + e.email + '</td><td>' + (e.created_at || '') + '</td></tr>'
  ).join('');
}

document.getElementById('login-form').addEventListener('submit', async (ev) => {
  ev.preventDefault();
  const errEl = document.getElementById('l-error');
  errEl.style.display = 'none';
  const res = await fetch('/admin/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: document.getElementById('l-email').value, password: document.getElementById('l-pass').value }),
  });
  if (res.ok) {
    const r2 = await fetch('/admin/emails');
    if (r2.ok) showDash(await r2.json());
  } else {
    errEl.textContent = 'Invalid email or password';
    errEl.style.display = 'block';
  }
});

async function doLogout() {
  await fetch('/admin/logout', { method: 'POST' });
  dashView.style.display = 'none';
  loginView.style.display = 'block';
}

checkAuth();
</script>
</body>
</html>
"""
