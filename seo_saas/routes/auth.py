import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from seo_saas.services.google_auth import get_login_url, exchange_code, get_user_info
from seo_saas.deps import get_db

router = APIRouter(prefix="/auth", tags=["auth"])

SESSION_DAYS = 30


@router.get("/login")
async def login():
    """Redirect user to Google OAuth consent screen."""
    state = secrets.token_urlsafe(16)
    url = get_login_url(state=state)
    return RedirectResponse(url)


@router.get("/callback")
async def callback(request: Request, code: str = "", error: str = ""):
    """Handle Google OAuth callback — upsert user, create session, set cookie."""
    if error or not code:
        return RedirectResponse("/?error=auth_denied")

    try:
        token_data = await exchange_code(code)
    except Exception:
        return RedirectResponse("/?error=auth_failed")

    access_token = token_data["access_token"]
    refresh_token = token_data.get("refresh_token", "")
    expires_in = token_data.get("expires_in", 3600)
    token_expires = (datetime.utcnow() + timedelta(seconds=expires_in)).isoformat()

    try:
        user_info = await get_user_info(access_token)
    except Exception:
        return RedirectResponse("/?error=auth_failed")

    google_id = user_info["id"]
    email = user_info.get("email", "")
    name = user_info.get("name", "")
    picture = user_info.get("picture", "")

    db = get_db()

    # Upsert user
    async with db.execute("SELECT id FROM users WHERE google_id = ?", (google_id,)) as cur:
        existing = await cur.fetchone()

    if existing:
        user_id = existing[0]
        await db.execute(
            """UPDATE users
               SET access_token = ?, refresh_token = COALESCE(NULLIF(?, ''), refresh_token),
                   token_expires_at = ?, name = ?, picture_url = ?,
                   email = ?, last_login_at = datetime('now')
               WHERE id = ?""",
            (access_token, refresh_token, token_expires, name, picture, email, user_id),
        )
    else:
        async with db.execute(
            """INSERT INTO users (email, name, picture_url, google_id,
                                  access_token, refresh_token, token_expires_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (email, name, picture, google_id, access_token, refresh_token, token_expires),
        ) as cur:
            user_id = cur.lastrowid

    # Check if this email is a paying customer → mark lifetime
    async with db.execute("SELECT 1 FROM customers WHERE email = ?", (email,)) as cur:
        is_customer = await cur.fetchone()
    if is_customer:
        await db.execute("UPDATE users SET is_lifetime = 1 WHERE id = ?", (user_id,))

    # Create session
    session_token = secrets.token_urlsafe(32)
    expires_at = (datetime.utcnow() + timedelta(days=SESSION_DAYS)).isoformat()
    await db.execute(
        "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
        (session_token, user_id, expires_at),
    )
    await db.commit()

    response = RedirectResponse("/dashboard")
    response.set_cookie(
        "session",
        session_token,
        max_age=SESSION_DAYS * 86400,
        httponly=True,
        samesite="lax",
        secure=True,
    )
    return response


@router.get("/logout")
async def logout(request: Request):
    token = request.cookies.get("session")
    if token:
        db = get_db()
        await db.execute("DELETE FROM sessions WHERE token = ?", (token,))
        await db.commit()

    response = RedirectResponse("/")
    response.delete_cookie("session")
    return response


@router.get("/me")
async def me(request: Request):
    """Return current user info (for the dashboard)."""
    token = request.cookies.get("session")
    if not token:
        raise HTTPException(401, "Not authenticated")

    db = get_db()
    async with db.execute(
        """SELECT u.id, u.email, u.name, u.picture_url, u.is_lifetime
           FROM users u JOIN sessions s ON s.user_id = u.id
           WHERE s.token = ? AND s.expires_at > datetime('now')""",
        (token,),
    ) as cur:
        user = await cur.fetchone()

    if not user:
        raise HTTPException(401, "Session expired")

    return {
        "id": user[0],
        "email": user[1],
        "name": user[2],
        "picture_url": user[3],
        "is_lifetime": bool(user[4]),
    }
