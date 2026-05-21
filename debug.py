"""Script de diagnóstico — muestra los datos crudos guardados en el cache."""
import sqlite3, json
from pathlib import Path

DB = Path(__file__).parent / "data.nosync" / "cache.db"
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

print("=" * 60)
print("ACCOUNT SNAPSHOT")
for r in con.execute("SELECT * FROM account_snapshot").fetchall():
    d = dict(r)
    print(f"  platform: {d['platform']}")
    print(f"  username: {d['username']}")
    print(f"  followers: {d['followers']}")
    raw = json.loads(d.get('raw_json') or '{}')
    print(f"  raw_json keys: {list(raw.keys())}")
    print(f"  raw_json sample: {json.dumps(raw, ensure_ascii=False)[:500]}")
    print()

print("=" * 60)
print("ACCOUNT INSIGHTS 30D")
for r in con.execute("SELECT * FROM account_insights_30d").fetchall():
    d = dict(r)
    print(f"  reach={d['reach']} views={d['views']} likes={d['likes']}")
    raw = json.loads(d.get('raw_json') or '{}')
    print(f"  raw_json keys: {list(raw.keys())}")
    print(f"  raw_json sample: {json.dumps(raw, ensure_ascii=False)[:500]}")
    print()

print("=" * 60)
print("DAILY METRICS (primeras 2 filas)")
for r in con.execute("SELECT * FROM daily_metrics LIMIT 2").fetchall():
    d = dict(r)
    raw = json.loads(d.get('raw_json') or '{}')
    print(f"  date={d['date']} reach={d['reach']} likes={d['likes']}")
    print(f"  raw_json keys: {list(raw.keys())}")
    print(f"  raw_json sample: {json.dumps(raw, ensure_ascii=False)[:400]}")
    print()

print("=" * 60)
print("POSTS (primeras 2 filas)")
for r in con.execute("SELECT * FROM posts LIMIT 2").fetchall():
    d = dict(r)
    raw = json.loads(d.get('raw_json') or '{}')
    print(f"  id={d['id']} likes={d['likes']} comments={d['comments']}")
    print(f"  raw_json keys: {list(raw.keys())}")
    print(f"  raw_json sample: {json.dumps(raw, ensure_ascii=False)[:400]}")
    print()

print("=" * 60)
print("COMMENTS (primeras 2 filas)")
for r in con.execute("SELECT * FROM comments LIMIT 2").fetchall():
    d = dict(r)
    raw = json.loads(d.get('raw_json') or '{}')
    print(f"  id={d['id']} text={d['text'][:80] if d['text'] else ''}")
    print(f"  raw_json keys: {list(raw.keys())}")
    print()

print("=" * 60)
print("MESSAGES/DMs (primeras 2 filas)")
for r in con.execute("SELECT * FROM messages LIMIT 2").fetchall():
    d = dict(r)
    raw = json.loads(d.get('raw_json') or '{}')
    print(f"  id={d['id']} text={d['text'][:80] if d['text'] else ''}")
    print(f"  raw_json keys: {list(raw.keys())}")
    print()

con.close()
print("Diagnóstico completado.")
