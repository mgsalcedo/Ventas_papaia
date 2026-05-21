"""Muestra las respuestas crudas de Zernio para los endpoints que fallan."""
import os, json
from dotenv import load_dotenv
load_dotenv(override=True)
import zernio_client as z

account_id = os.getenv("ZERNIO_ACCOUNT_ID", "").strip()
print(f"Account ID: {account_id}\n")

def show(label, fn, *args, **kwargs):
    print(f"{'='*60}")
    print(f"ENDPOINT: {label}")
    try:
        r = fn(*args, **kwargs)
        text = json.dumps(r, ensure_ascii=False, indent=2)
        print(text[:1500])
        if len(text) > 1500:
            print(f"... (truncado, total {len(text)} chars)")
    except Exception as e:
        print(f"ERROR: {e}")
    print()

show("daily_metrics", z.get_daily_metrics, account_id, "instagram")
show("demographics", z.get_demographics, account_id)
show("best_time_to_post", z.get_best_time_to_post, account_id, "instagram")
show("posting_frequency", z.get_posting_frequency, account_id, "instagram")
show("follower_history", z.get_follower_history, account_id)
show("inbox_comments", z.list_inbox_comments, account_id, "instagram")
