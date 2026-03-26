import json
import logging
from openai import AsyncOpenAI
from seo_saas.config import OPENAI_API_KEY

log = logging.getLogger(__name__)
_client = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    return _client


async def chat(system_prompt: str, user_prompt: str, model: str = "gpt-4o-mini", max_tokens: int = 1024) -> str:
    """Send a chat completion and return the assistant message text."""
    client = _get_client()
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
            temperature=0.3,
        )
        return resp.choices[0].message.content or ""
    except Exception as e:
        log.error("OpenAI API error: %s", e)
        raise


async def chat_json(system_prompt: str, user_prompt: str, model: str = "gpt-4o-mini", max_tokens: int = 2048) -> dict | list:
    """Send a chat completion and parse the response as JSON."""
    text = await chat(system_prompt, user_prompt + "\n\nRespond ONLY with valid JSON, no markdown fences.", model, max_tokens)
    # Strip markdown fences if present
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    return json.loads(text)
