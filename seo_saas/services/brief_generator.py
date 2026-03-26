import json
import logging
from seo_saas.services.openai_client import chat_json

log = logging.getLogger(__name__)


async def generate_brief(db, property_id: int, target_keyword: str, user_id: int) -> dict:
    """Generate an AI content brief for a target keyword."""
    # Verify ownership
    async with db.execute(
        "SELECT * FROM properties WHERE id = ? AND user_id = ?",
        (property_id, user_id),
    ) as cur:
        prop = await cur.fetchone()
    if not prop:
        raise ValueError("Property not found")
    prop = dict(prop)

    # Get existing keywords for context
    async with db.execute(
        "SELECT keyword, cluster, current_position FROM keywords WHERE property_id = ? LIMIT 50",
        (property_id,),
    ) as cur:
        existing = [dict(r) for r in await cur.fetchall()]

    context = f"Website: {prop['domain']}\nTarget keyword: {target_keyword}"
    if existing:
        context += "\nExisting keywords the site ranks for: " + ", ".join(
            k["keyword"] for k in existing[:30]
        )

    brief = await chat_json(
        system_prompt=(
            "You are an expert SEO content strategist. Generate a comprehensive content brief "
            "that will help a writer create an article optimized for the target keyword."
        ),
        user_prompt=(
            f"{context}\n\n"
            "Generate a content brief with:\n"
            "- title: SEO-optimized article title\n"
            "- meta_description: suggested meta description (under 160 chars)\n"
            "- target_word_count: recommended word count\n"
            "- secondary_keywords: array of 5-10 related keywords to include\n"
            "- outline: array of objects with heading (text), level (h2 or h3), and notes (what to cover)\n"
            "- competitive_angle: what makes this content unique/better than competitors\n\n"
            "Return as a single JSON object."
        ),
        model="gpt-4o-mini",
        max_tokens=2048,
    )

    if not isinstance(brief, dict):
        raise ValueError("Invalid brief format from AI")

    # Store in database
    async with db.execute(
        """INSERT INTO briefs (property_id, title, target_keyword, secondary_keywords,
           target_word_count, outline_json, status)
           VALUES (?, ?, ?, ?, ?, ?, 'draft')""",
        (
            property_id,
            brief.get("title", target_keyword),
            target_keyword,
            json.dumps(brief.get("secondary_keywords", [])),
            brief.get("target_word_count", 1500),
            json.dumps(brief.get("outline", [])),
        ),
    ) as cur:
        brief_id = cur.lastrowid
    await db.commit()

    brief["id"] = brief_id
    return brief


async def list_briefs(db, property_id: int, user_id: int) -> list[dict]:
    """List all briefs for a property."""
    async with db.execute(
        "SELECT id FROM properties WHERE id = ? AND user_id = ?", (property_id, user_id)
    ) as cur:
        if not await cur.fetchone():
            raise ValueError("Property not found")

    async with db.execute(
        """SELECT id, title, target_keyword, target_word_count, status, created_at
           FROM briefs WHERE property_id = ? ORDER BY created_at DESC""",
        (property_id,),
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]


async def get_brief(db, brief_id: int, user_id: int) -> dict:
    """Get a single brief with full details."""
    async with db.execute(
        """SELECT b.* FROM briefs b
           JOIN properties p ON p.id = b.property_id
           WHERE b.id = ? AND p.user_id = ?""",
        (brief_id, user_id),
    ) as cur:
        row = await cur.fetchone()
    if not row:
        raise ValueError("Brief not found")

    result = dict(row)
    # Parse JSON fields
    for field in ("secondary_keywords", "outline_json"):
        if result.get(field):
            try:
                result[field] = json.loads(result[field])
            except (json.JSONDecodeError, TypeError):
                pass
    return result


async def delete_brief(db, brief_id: int, user_id: int):
    """Delete a brief."""
    await db.execute(
        """DELETE FROM briefs WHERE id = ? AND property_id IN
           (SELECT id FROM properties WHERE user_id = ?)""",
        (brief_id, user_id),
    )
    await db.commit()
