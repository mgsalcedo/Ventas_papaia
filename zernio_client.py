import os
import time
import requests
from dotenv import load_dotenv

load_dotenv(override=True)

BASE_URL = "https://api.zernio.com/v1"
BACKOFF = [2, 3, 5, 9]


def _headers():
    key = os.getenv("ZERNIO_API_KEY", "")
    if not key:
        raise RuntimeError("ZERNIO_API_KEY no está en .env")
    return {"Authorization": f"Bearer {key}"}


def _get(path: str, params: dict = None) -> dict:
    url = f"{BASE_URL}{path}"
    last_exc = None
    for attempt, wait in enumerate([0] + BACKOFF):
        if wait:
            time.sleep(wait)
        try:
            r = requests.get(url, headers=_headers(), params=params, timeout=30)
            if r.status_code in (429, 500, 502, 503, 529):
                last_exc = RuntimeError(f"[{r.status_code}] {r.text[:200]}")
                continue
            if not r.ok:
                raise RuntimeError(f"[{r.status_code}] {r.text[:400]}")
            return r.json()
        except requests.RequestException as e:
            last_exc = e
    raise last_exc or RuntimeError(f"No se pudo conectar a {url}")


# ── Account discovery ────────────────────────────────────────────────────────

def list_accounts(platform: str = "instagram") -> list:
    data = _get("/accounts", {"platform": platform})
    if isinstance(data, list):
        return data
    return data.get("data", data.get("accounts", []))


def get_account_health(account_id: str, platform: str = "instagram") -> dict:
    return _get(f"/accounts/{account_id}/health", {"platform": platform})


# ── Analytics cross-platform ─────────────────────────────────────────────────

def get_daily_metrics(account_id: str, platform: str = "instagram") -> dict:
    return _get("/analytics/daily-metrics", {"accountId": account_id, "platform": platform})


def get_best_time_to_post(account_id: str, platform: str = "instagram") -> dict:
    return _get("/analytics/best-time", {"accountId": account_id, "platform": platform})


def get_posting_frequency(account_id: str, platform: str = "instagram") -> dict:
    return _get("/analytics/posting-frequency", {"accountId": account_id, "platform": platform})


def get_content_decay(account_id: str, platform: str = "instagram") -> dict:
    return _get("/analytics/content-decay", {"accountId": account_id, "platform": platform})


def get_usage_stats() -> dict:
    return _get("/usage-stats")


# ── Inbox ────────────────────────────────────────────────────────────────────

def list_inbox_comments(account_id: str, platform: str = "instagram") -> dict:
    return _get("/inbox/comments", {"accountId": account_id, "platform": platform})


def get_post_comments(post_id: str, account_id: str, platform: str = "instagram") -> dict:
    return _get(f"/inbox/comments/{post_id}", {"accountId": account_id, "platform": platform})


# ── Instagram-only ───────────────────────────────────────────────────────────

def get_account_insights(account_id: str) -> dict:
    return _get("/analytics/instagram/account-insights", {"accountId": account_id})


def get_demographics(account_id: str) -> dict:
    return _get("/analytics/instagram/demographics", {"accountId": account_id})


def get_follower_history(account_id: str) -> dict:
    return _get("/analytics/instagram/follower-history", {"accountId": account_id})


def list_conversations(account_id: str) -> dict:
    return _get("/inbox/conversations", {"accountId": account_id})


def get_conversation_messages(conversation_id: str, account_id: str) -> dict:
    return _get(f"/inbox/conversations/{conversation_id}/messages", {"accountId": account_id})


# ── YouTube-only ─────────────────────────────────────────────────────────────

def get_youtube_channel_insights(account_id: str) -> dict:
    return _get("/analytics/youtube/channel-insights", {"accountId": account_id})


def get_youtube_demographics(account_id: str) -> dict:
    return _get("/analytics/youtube/demographics", {"accountId": account_id})


def get_youtube_daily_views(account_id: str, video_id: str = None) -> dict:
    params = {"accountId": account_id}
    if video_id:
        params["videoId"] = video_id
    return _get("/analytics/youtube/daily-views", params)
