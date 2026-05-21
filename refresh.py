#!/usr/bin/env python3
"""
Descarga datos de Zernio y los guarda en el cache SQLite local.
Uso: python refresh.py
"""
import os
import json
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)

import zernio_client as z
import cache


def _discover_and_save_account_id(platform: str, env_key: str) -> str | None:
    print(f"  Buscando tu cuenta de {platform} en Zernio...")
    try:
        accounts = z.list_accounts(platform)
    except Exception as e:
        print(f"  Error al listar cuentas {platform}: {e}")
        return None

    if not accounts:
        print(f"  No encontré ninguna cuenta de {platform} en Zernio.")
        return None

    account = accounts[0]
    account_id = account.get("_id") or account.get("id") or account.get("account_id", "")
    if not account_id:
        print(f"  No pude extraer el ID de la cuenta: {account}")
        return None

    # Guarda en .env
    env_path = Path(__file__).parent / ".env"
    lines = env_path.read_text().splitlines()
    new_lines = []
    replaced = False
    for line in lines:
        if line.startswith(f"{env_key}="):
            new_lines.append(f"{env_key}={account_id}")
            replaced = True
        else:
            new_lines.append(line)
    if not replaced:
        new_lines.append(f"{env_key}={account_id}")
    env_path.write_text("\n".join(new_lines) + "\n")

    print(f"  Cuenta {platform} encontrada: {account.get('username', account_id)} (ID guardado en .env)")
    return account_id


def _safe(label: str, fn, *args, **kwargs):
    try:
        result = fn(*args, **kwargs)
        print(f"  [ok] {label}")
        return result
    except Exception as e:
        msg = str(e)
        print(f"  [!] {label}: {msg[:120]}")
        return None


def refresh_instagram(account_id: str):
    print("\n📷 Actualizando Instagram...")

    # Account snapshot
    accounts = _safe("listar cuentas IG", z.list_accounts, "instagram")
    if accounts:
        cache.upsert_account_snapshot("instagram", accounts[0])

    # Health
    health = _safe("salud cuenta IG", z.get_account_health, account_id, "instagram")
    if health:
        cache.upsert_health("instagram", health)

    # Insights 30d
    insights = _safe("insights 30 días", z.get_account_insights, account_id)
    if insights:
        data = insights.get("data") or insights.get("insights") or insights
        if isinstance(data, dict):
            cache.upsert_insights_30d("instagram", data)

    # Daily metrics
    dm = _safe("métricas diarias", z.get_daily_metrics, account_id, "instagram")
    if dm:
        rows = dm.get("data") or dm.get("metrics") or dm.get("daily_metrics") or []
        if isinstance(dm, list):
            rows = dm
        if rows:
            cache.upsert_daily_metrics("instagram", rows)

    # Demographics
    demo = _safe("demografía IG", z.get_demographics, account_id)
    if demo:
        data = demo.get("data") or demo
        cache.upsert_demographics("instagram", data if isinstance(data, dict) else demo)

    # Follower history
    fh = _safe("historial seguidores", z.get_follower_history, account_id)
    if fh:
        rows = fh.get("data") or fh.get("history") or []
        if isinstance(fh, list):
            rows = fh
        if rows:
            cache.upsert_follower_history("instagram", rows)

    # Best time
    bt = _safe("mejor hora IG", z.get_best_time_to_post, account_id, "instagram")
    if bt:
        rows = bt.get("data") or bt.get("best_times") or []
        if isinstance(bt, list):
            rows = bt
        if rows:
            cache.upsert_best_time("instagram", rows)

    # Posting frequency
    pf = _safe("frecuencia de publicación IG", z.get_posting_frequency, account_id, "instagram")
    if pf:
        rows = pf.get("data") or pf.get("frequency") or []
        if isinstance(pf, list):
            rows = pf
        if isinstance(rows, dict):
            rows = [rows]
        if rows:
            cache.upsert_posting_frequency("instagram", rows)

    # Content decay
    cd = _safe("decaimiento de contenido IG", z.get_content_decay, account_id, "instagram")
    if cd:
        rows = cd.get("data") or cd.get("buckets") or []
        if isinstance(cd, list):
            rows = cd
        if rows:
            cache.upsert_content_decay("instagram", rows)

    # Comments (inbox)
    comments_resp = _safe("comentarios (inbox)", z.list_inbox_comments, account_id, "instagram")
    if comments_resp:
        posts_with_comments = (
            comments_resp.get("data") or
            comments_resp.get("posts") or
            comments_resp.get("comments") or
            []
        )
        if isinstance(comments_resp, list):
            posts_with_comments = comments_resp

        all_comments = []
        for item in posts_with_comments:
            if isinstance(item, dict):
                if "comments" in item:
                    for c in (item["comments"] or []):
                        c["post_id"] = item.get("post_id") or item.get("id", "")
                        all_comments.append(c)
                elif "text" in item or "message" in item:
                    all_comments.append(item)

        # Also save posts from the comments endpoint
        posts_data = []
        for item in posts_with_comments:
            if isinstance(item, dict) and ("media_type" in item or "permalink" in item or "thumbnail_url" in item):
                posts_data.append(item)
        if posts_data:
            cache.upsert_posts("instagram", posts_data)

        if all_comments:
            cache.upsert_comments("instagram", all_comments)
            print(f"     → {len(all_comments)} comentarios guardados")

    # DM conversations
    convos = _safe("conversaciones DM", z.list_conversations, account_id)
    if convos:
        convo_list = convos.get("data") or convos.get("conversations") or []
        if isinstance(convos, list):
            convo_list = convos
        if convo_list:
            cache.upsert_conversations(convo_list)
            dm_count = 0
            for convo in convo_list[:50]:  # limit to avoid rate limits
                cid = convo.get("id") or convo.get("_id", "")
                if not cid:
                    continue
                msgs = _safe(f"  mensajes conv {cid[:8]}...", z.get_conversation_messages, cid, account_id)
                if msgs:
                    msg_list = msgs.get("data") or msgs.get("messages") or []
                    if isinstance(msgs, list):
                        msg_list = msgs
                    if msg_list:
                        cache.upsert_messages(cid, msg_list)
                        dm_count += len(msg_list)
            print(f"     → {dm_count} mensajes de DMs guardados")


def run():
    cache.init_db()

    account_id_ig = os.getenv("ZERNIO_ACCOUNT_ID", "").strip()
    account_id_yt = os.getenv("ZERNIO_ACCOUNT_ID_YOUTUBE", "").strip()

    # Auto-discover account IDs if not set
    if not account_id_ig:
        account_id_ig = _discover_and_save_account_id("instagram", "ZERNIO_ACCOUNT_ID") or ""
        if not account_id_ig:
            print("\n❌ No se pudo obtener el account_id de Instagram. Verifica tu API key de Zernio.")
            sys.exit(1)
        # Reload env after writing
        load_dotenv(override=True)
        account_id_ig = os.getenv("ZERNIO_ACCOUNT_ID", "").strip()

    rid = cache.log_refresh_start()
    try:
        refresh_instagram(account_id_ig)
        cache.log_refresh_end(rid, "ok")
        print("\n✅ Refresh completado.")
    except Exception as e:
        cache.log_refresh_end(rid, "error", str(e))
        print(f"\n❌ Error durante el refresh: {e}")
        raise


if __name__ == "__main__":
    run()
