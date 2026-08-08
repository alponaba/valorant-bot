from __future__ import annotations

import hashlib
from typing import Sequence

from v4_store import store


async def unique_variant(discord_id: int | str, scope: str, options: Sequence[str], salt: str = "") -> str:
    if not options:
        return ""
    old = set(await store.recent_generated_hashes(discord_id, scope, 30))
    count = await store.generated_count(discord_id, scope)
    for step in range(max(8, len(options) * 3)):
        seed = f"{discord_id}:{scope}:{salt}:{count + step}"
        idx = int(hashlib.sha256(seed.encode('utf-8')).hexdigest()[:8], 16) % len(options)
        text = options[idx]
        h = hashlib.sha256(text.encode('utf-8')).hexdigest()[:20]
        if h not in old:
            await store.save_generated_response(discord_id, scope, text)
            return text
    # If all finite templates were used, append a harmless analysis revision marker so exact text is not repeated.
    base = options[count % len(options)]
    text = f"{base}\n\nAnaliz notu: Bu öneri önceki cevap geçmişine göre yeniden sıralandı ({count + 1})."
    await store.save_generated_response(discord_id, scope, text)
    return text
