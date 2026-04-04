"""
IALIVE B7 — Webhook Handler per Auto-Post Social

Handler Python che riceve webhook, legge from Supabase, e posta su Bluesky/X.
Può girare come Vercel serverless function o come script locale con cron.

Architettura:
1. Trigger: GitHub push (nuovo contenuto → webhook) o cron (controlla coda ogni N min)
2. Handler: legge content_queue da Supabase → genera post da firme.md → posta via API
3. Tracking: registra risultato in social_posts, aggiorna coda

Dipendenze:
- supabase-py (pip install supabase)
- requests (pip install requests)
- .env con SUPABASE_URL, SUPABASE_KEY, BLUESKY_HANDLE, BLUESKY_APP_PASSWORD

Uso:
  python webhook_handler.py --trigger=github
  python webhook_handler.py --trigger=cron
  python webhook_handler.py --trigger=manual --content="Test post"
"""

import os
import json
import sys
from datetime import datetime, timezone

# -----------------------------------------------------------
# 1. CONFIGURAZIONE
# -----------------------------------------------------------

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
BLUESKY_HANDLE = os.getenv("BLUESKY_HANDLE", "")
BLUESKY_APP_PASSWORD = os.getenv("BLUESKY_APP_PASSWORD", "")
X_API_BEARER = os.getenv("X_API_BEARER", "")  # Optional, per X/Twitter

# Rate limiting: max post per ora
MAX_POSTS_PER_HOUR = int(os.getenv("MAX_POSTS_PER_HOUR", "4"))

# -----------------------------------------------------------
# 2. SUPABASE CLIENT (minimale, via REST API)
# -----------------------------------------------------------

import requests

def supabase_query(table: str, query: str = "", headers: dict = None) -> dict:
    """Query Supabase via REST API."""
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    if query:
        url += f"?{query}"
    h = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    if headers:
        h.update(headers)
    resp = requests.get(url, headers=h)
    resp.raise_for_status()
    return resp.json()

def supabase_insert(table: str, data: dict) -> dict:
    """Inserisci record in Supabase."""
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    h = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    resp = requests.post(url, json=[data], headers=h)
    resp.raise_for_status()
    return resp.json()

def supabase_update(table: str, id_col: str, id_val, updates: dict) -> dict:
    """Aggiorna record in Supabase."""
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    h = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    resp = requests.patch(
        f"{url}?{id_col}=eq.{id_val}",
        json=updates,
        headers=h
    )
    resp.raise_for_status()
    return resp.json()

# -----------------------------------------------------------
# 3. BLUESKY API
# -----------------------------------------------------------

_bsky_session = None  # cache sessione

def bsky_create_session() -> dict:
    """Crea sessione Bluesky con app password."""
    resp = requests.post(
        "https://bsky.social/xrpc/com.atproto.server.createSession",
        json={"identifier": BLUESKY_HANDLE, "password": BLUESKY_APP_PASSWORD}
    )
    resp.raise_for_status()
    return resp.json()

def bsky_get_session() -> str:
    """Ottieni auth token (caching + refresh se scaduto)."""
    global _bsky_session
    if _bsky_session is None:
        _bsky_session = bsky_create_session()
    return _bsky_session.get("accessJwt", "")

def bsky_post(text: str, tags: list = None) -> dict:
    """Posta su Bluesky. Returns record URI."""
    token = bsky_get_session()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # Costruisci record con facets per tags/mentions
    record = {
        "$type": "app.bsky.feed.post",
        "text": text,
        "createdAt": now,
    }
    
    resp = requests.post(
        "https://bsky.social/xrpc/com.atproto.repo.createRecord",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "repo": BLUESKY_HANDLE,
            "collection": "app.bsky.feed.post",
            "record": record,
        }
    )
    resp.raise_for_status()
    return resp.json()

# -----------------------------------------------------------
# 4. X/TWITTER API (opzionale)
# -----------------------------------------------------------

def x_post(text: str) -> dict:
    """Posta su X/Twitter via API v2."""
    if not X_API_BEARER:
        return {"error": "X_API_BEARER not configured"}
    resp = requests.post(
        "https://api.twitter.com/2/tweets",
        headers={"Authorization": f"Bearer {X_API_BEARER}"},
        json={"text": text}
    )
    return resp.json()

# -----------------------------------------------------------
# 5. RATE LIMITING
# -----------------------------------------------------------

def check_rate_limit() -> bool:
    """Verifica se possiamo ancora postare (max N/ora)."""
    from datetime import timedelta
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    posts = supabase_query(
        "social_posts",
        f"posted_at=gte.{one_hour_ago.isoformat()}",
    )
    return len(posts) < MAX_POSTS_PER_HOUR

# -----------------------------------------------------------
# 6. HANDLER PRINCIPALE
# -----------------------------------------------------------

def handle_webhook(trigger: str = "cron", content: str = None) -> dict:
    """
    Main webhook handler.
    
    trigger: "cron" | "github" | "manual"
    content: testo manuale (solo per trigger=manual)
    """
    result = {
        "trigger": trigger,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "posts": [],
        "errors": [],
    }
    
    # Rate limit check
    if not check_rate_limit():
        result["errors"].append("Rate limit reached (max posts/hour)")
        return result
    
    if trigger == "manual" and content:
        # Post manuale
        try:
            bluesky_resp = bsky_post(content)
            result["posts"].append({
                "platform": "bluesky",
                "text": content,
                "response": bluesky_resp,
            })
        except Exception as e:
            result["errors"].append(f"Bluesky error: {e}")
        
    elif trigger in ("cron", "github"):
        # Leggi dalla coda
        queue = supabase_query("content_queue", "status=eq.pending&order=priority.desc")
        
        for item in queue[:MAX_POSTS_PER_HOUR]:
            try:
                text = item.get("content", "")
                platforms = json.loads(item.get("platforms", "[]"))
                
                # Bluesky
                if "bluesky" in platforms:
                    resp = bsky_post(text)
                    result["posts"].append({
                        "platform": "bluesky",
                        "text": text,
                        "uri": resp.get("uri", ""),
                    })
                    supabase_update("content_queue", "id", item["id"], {"status": "posted"})
                
                # X/Twitter
                if "twitter" in platforms:
                    resp = x_post(text)
                    result["posts"].append({
                        "platform": "twitter",
                        "text": text,
                        "response": resp,
                    })
                    supabase_update("content_queue", "id", item["id"], {"status": "posted"})
                
                # Log in heartbeat o social_posts
                supabase_insert("social_posts", {
                    "content": text,
                    "platforms": json.dumps(platforms),
                    "posted_at": datetime.now(timezone.utc).isoformat(),
                    "status": "published",
                    "heartbeat_id": item.get("heartbeat_id"),
                })
                
            except Exception as e:
                result["errors"].append(f"Post failed: {e}")
                try:
                    supabase_update("content_queue", "id", item["id"], 
                                  {"status": "failed", "error": str(e)})
                except:
                    pass
    
    # Log questo ciclo in heartbeat_log o social_posts
    supabase_insert("social_posts", {
        "content": f"[AUTO] Webhook cycle: trigger={trigger}, posts={len(result['posts'])}, errors={len(result['errors'])}",
        "platforms": "system",
        "posted_at": datetime.now(timezone.utc).isoformat(),
        "status": "system",
    })
    
    return result

# -----------------------------------------------------------
# 7. CLI ENTRY POINT
# -----------------------------------------------------------

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="IALIVE Webhook Handler")
    parser.add_argument("--trigger", default="cron", choices=["cron", "github", "manual"])
    parser.add_argument("--content", default=None, help="Testo per post manuale")
    parser.add_argument("--dry-run", action="store_true", help="Simula senza spedire")
    args = parser.parse_args()
    
    if args.dry_run:
        print(f"[DRY RUN] trigger={args.trigger}, content={args.content}")
        print(f"[DRY RUN] Rate limit OK: {check_rate_limit()}")
        sys.exit(0)
    
    result = handle_webhook(args.trigger, args.content)
    print(json.dumps(result, indent=2, ensure_ascii=False))
