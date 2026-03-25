from fastapi import HTTPException, Request
import seo_saas.storage.database as store


def get_db():
    if not store.db:
        raise HTTPException(500, "Database not ready")
    return store.db


async def get_current_user(request: Request):
    token = request.cookies.get("session")
    if not token:
        raise HTTPException(401, "Not authenticated")

    db = get_db()
    async with db.execute(
        """SELECT u.* FROM users u
           JOIN sessions s ON s.user_id = u.id
           WHERE s.token = ? AND s.expires_at > datetime('now')""",
        (token,),
    ) as cursor:
        user = await cursor.fetchone()

    if not user:
        raise HTTPException(401, "Session expired")
    return dict(user)
