import sqlite3
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "data.nosync" / "cache.db"


def _conn():
    DB_PATH.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    return con


def _col_exists(con, table: str, col: str) -> bool:
    rows = con.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r["name"] == col for r in rows)


def init_db():
    con = _conn()
    with con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS meta (
                key   TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE TABLE IF NOT EXISTS account_snapshot (
                platform       TEXT PRIMARY KEY,
                account_id     TEXT,
                username       TEXT,
                display_name   TEXT,
                profile_pic    TEXT,
                followers      INTEGER,
                raw_json       TEXT,
                updated_at     TEXT
            );

            CREATE TABLE IF NOT EXISTS account_health (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                platform   TEXT,
                status     TEXT,
                score      REAL,
                raw_json   TEXT,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS account_insights_30d (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                platform     TEXT DEFAULT 'instagram',
                reach        INTEGER,
                impressions  INTEGER,
                views        INTEGER,
                engaged      INTEGER,
                interactions INTEGER,
                likes        INTEGER,
                comments     INTEGER,
                saves        INTEGER,
                shares       INTEGER,
                raw_json     TEXT,
                updated_at   TEXT
            );

            CREATE TABLE IF NOT EXISTS youtube_channel_insights_daily (
                date        TEXT,
                account_id  TEXT,
                views       INTEGER,
                watch_hours REAL,
                subs_gained INTEGER,
                subs_lost   INTEGER,
                raw_json    TEXT,
                PRIMARY KEY (date, account_id)
            );

            CREATE TABLE IF NOT EXISTS youtube_channel_totals_30d (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id  TEXT,
                views       INTEGER,
                watch_hours REAL,
                subs_net    INTEGER,
                raw_json    TEXT,
                updated_at  TEXT
            );

            CREATE TABLE IF NOT EXISTS daily_metrics (
                date        TEXT,
                platform    TEXT,
                reach       INTEGER,
                impressions INTEGER,
                views       INTEGER,
                engaged     INTEGER,
                likes       INTEGER,
                comments    INTEGER,
                saves       INTEGER,
                shares      INTEGER,
                followers   INTEGER,
                raw_json    TEXT,
                PRIMARY KEY (date, platform)
            );

            CREATE TABLE IF NOT EXISTS demographics_age (
                bucket   TEXT,
                platform TEXT,
                pct      REAL,
                count    INTEGER,
                PRIMARY KEY (bucket, platform)
            );

            CREATE TABLE IF NOT EXISTS demographics_gender (
                bucket   TEXT,
                platform TEXT,
                pct      REAL,
                count    INTEGER,
                PRIMARY KEY (bucket, platform)
            );

            CREATE TABLE IF NOT EXISTS demographics_country (
                bucket   TEXT,
                platform TEXT,
                pct      REAL,
                count    INTEGER,
                PRIMARY KEY (bucket, platform)
            );

            CREATE TABLE IF NOT EXISTS demographics_city (
                bucket   TEXT,
                platform TEXT,
                pct      REAL,
                count    INTEGER,
                PRIMARY KEY (bucket, platform)
            );

            CREATE TABLE IF NOT EXISTS posts (
                id           TEXT,
                platform     TEXT,
                caption      TEXT,
                media_type   TEXT,
                permalink    TEXT,
                thumbnail    TEXT,
                timestamp    TEXT,
                likes        INTEGER DEFAULT 0,
                comments     INTEGER DEFAULT 0,
                saves        INTEGER DEFAULT 0,
                shares       INTEGER DEFAULT 0,
                reach        INTEGER DEFAULT 0,
                views        INTEGER DEFAULT 0,
                engagement   REAL DEFAULT 0,
                raw_json     TEXT,
                PRIMARY KEY (id)
            );

            CREATE TABLE IF NOT EXISTS comments (
                id          TEXT PRIMARY KEY,
                post_id     TEXT,
                platform    TEXT,
                username    TEXT,
                text        TEXT,
                timestamp   TEXT,
                likes       INTEGER DEFAULT 0,
                raw_json    TEXT
            );

            CREATE TABLE IF NOT EXISTS conversations (
                id          TEXT PRIMARY KEY,
                platform    TEXT DEFAULT 'instagram',
                username    TEXT,
                updated_at  TEXT,
                raw_json    TEXT
            );

            CREATE TABLE IF NOT EXISTS messages (
                id              TEXT PRIMARY KEY,
                conversation_id TEXT,
                platform        TEXT DEFAULT 'instagram',
                from_user       TEXT,
                text            TEXT,
                timestamp       TEXT,
                raw_json        TEXT
            );

            CREATE TABLE IF NOT EXISTS best_time (
                day_of_week INTEGER,
                hour        INTEGER,
                platform    TEXT,
                score       REAL,
                PRIMARY KEY (day_of_week, hour, platform)
            );

            CREATE TABLE IF NOT EXISTS posting_frequency (
                posts_per_week REAL,
                platform       TEXT,
                avg_engagement REAL,
                raw_json       TEXT,
                PRIMARY KEY (posts_per_week, platform)
            );

            CREATE TABLE IF NOT EXISTS content_decay (
                bucket_order INTEGER,
                platform     TEXT,
                label        TEXT,
                avg_reach    REAL,
                avg_likes    REAL,
                raw_json     TEXT,
                PRIMARY KEY (bucket_order, platform)
            );

            CREATE TABLE IF NOT EXISTS follower_history (
                date      TEXT,
                platform  TEXT,
                followers INTEGER,
                gained    INTEGER DEFAULT 0,
                lost      INTEGER DEFAULT 0,
                PRIMARY KEY (date, platform)
            );

            CREATE TABLE IF NOT EXISTS ideas (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                generated_at      TEXT,
                batch_id          TEXT,
                source_bucket     TEXT NOT NULL DEFAULT 'top_content',
                platforms         TEXT,
                angle             TEXT,
                format            TEXT,
                rationale         TEXT,
                basis_post_ids    TEXT,
                basis_comment_ids TEXT,
                basis_message_ids TEXT,
                evidence_quotes   TEXT,
                why_good_idea     TEXT,
                suggested_angle   TEXT,
                discarded         INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS idea_discards (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                idea_id       INTEGER,
                angle         TEXT,
                source_bucket TEXT,
                platform      TEXT,
                discarded_at  TEXT,
                reason_quick  TEXT,
                reason_text   TEXT
            );

            CREATE TABLE IF NOT EXISTS refresh_log (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT,
                ended_at   TEXT,
                status     TEXT,
                error      TEXT
            );

            CREATE TABLE IF NOT EXISTS transcriptions (
                post_id    TEXT PRIMARY KEY,
                platform   TEXT,
                text       TEXT,
                created_at TEXT
            );
        """)

        # Idempotent migrations for ideas table
        for col, definition in [
            ("evidence_quotes", "TEXT"),
            ("why_good_idea", "TEXT"),
            ("suggested_angle", "TEXT"),
        ]:
            if not _col_exists(con, "ideas", col):
                con.execute(f"ALTER TABLE ideas ADD COLUMN {col} {definition}")

    con.close()


# ── Meta ─────────────────────────────────────────────────────────────────────

def set_meta(key: str, value: str):
    con = _conn()
    with con:
        con.execute("INSERT OR REPLACE INTO meta (key,value) VALUES (?,?)", (key, value))
    con.close()


def get_meta(key: str, default=None):
    con = _conn()
    row = con.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    con.close()
    return row["value"] if row else default


# ── Account snapshot ──────────────────────────────────────────────────────────

def upsert_account_snapshot(platform: str, data: dict):
    con = _conn()
    with con:
        con.execute("""
            INSERT OR REPLACE INTO account_snapshot
            (platform, account_id, username, display_name, profile_pic, followers, raw_json, updated_at)
            VALUES (?,?,?,?,?,?,?,?)
        """, (
            platform,
            data.get("_id") or data.get("id") or data.get("account_id", ""),
            data.get("username", ""),
            data.get("displayName") or data.get("name") or data.get("display_name", ""),
            data.get("profilePicture") or data.get("profile_picture_url") or data.get("profile_pic", ""),
            data.get("followersCount") or data.get("followers_count") or data.get("followers", 0),
            json.dumps(data),
            datetime.now(timezone.utc).isoformat(),
        ))
    con.close()


def get_account_snapshot(platform: str = "instagram") -> dict | None:
    con = _conn()
    row = con.execute("SELECT * FROM account_snapshot WHERE platform=?", (platform,)).fetchone()
    con.close()
    return dict(row) if row else None


# ── Health ────────────────────────────────────────────────────────────────────

def upsert_health(platform: str, data: dict):
    con = _conn()
    with con:
        con.execute("DELETE FROM account_health WHERE platform=?", (platform,))
        con.execute("""
            INSERT INTO account_health (platform, status, score, raw_json, updated_at)
            VALUES (?,?,?,?,?)
        """, (
            platform,
            data.get("status", "unknown"),
            data.get("score") or data.get("health_score", 0),
            json.dumps(data),
            datetime.now(timezone.utc).isoformat(),
        ))
    con.close()


def get_health(platform: str = "instagram") -> dict | None:
    con = _conn()
    row = con.execute("SELECT * FROM account_health WHERE platform=? ORDER BY id DESC LIMIT 1", (platform,)).fetchone()
    con.close()
    return dict(row) if row else None


# ── Insights 30d ──────────────────────────────────────────────────────────────

def upsert_insights_30d(platform: str, data: dict):
    con = _conn()
    with con:
        con.execute("DELETE FROM account_insights_30d WHERE platform=?", (platform,))
        con.execute("""
            INSERT INTO account_insights_30d
            (platform, reach, impressions, views, engaged, interactions, likes, comments, saves, shares, raw_json, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            platform,
            data.get("reach", 0),
            data.get("impressions", 0),
            data.get("views", 0) or data.get("video_views", 0),
            data.get("engaged_users", 0) or data.get("engaged", 0),
            data.get("total_interactions", 0) or data.get("interactions", 0),
            data.get("likes", 0),
            data.get("comments", 0),
            data.get("saves", 0),
            data.get("shares", 0),
            json.dumps(data),
            datetime.now(timezone.utc).isoformat(),
        ))
    con.close()


def get_insights_30d(platform: str = "instagram") -> dict | None:
    con = _conn()
    row = con.execute(
        "SELECT * FROM account_insights_30d WHERE platform=? ORDER BY id DESC LIMIT 1", (platform,)
    ).fetchone()
    con.close()
    return dict(row) if row else None


# ── Daily metrics ─────────────────────────────────────────────────────────────

def upsert_daily_metrics(platform: str, rows: list[dict]):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=180)).date().isoformat()
    con = _conn()
    with con:
        con.execute("DELETE FROM daily_metrics WHERE platform=? AND date<?", (platform, cutoff))
        for r in rows:
            con.execute("""
                INSERT OR REPLACE INTO daily_metrics
                (date, platform, reach, impressions, views, engaged, likes, comments, saves, shares, followers, raw_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                r.get("date", ""),
                platform,
                r.get("reach", 0),
                r.get("impressions", 0),
                r.get("views", 0) or r.get("video_views", 0),
                r.get("engaged_users", 0) or r.get("engaged", 0),
                r.get("likes", 0),
                r.get("comments", 0),
                r.get("saves", 0),
                r.get("shares", 0),
                r.get("followers", 0) or r.get("followers_count", 0),
                json.dumps(r),
            ))
    con.close()


def get_daily_metrics(platform: str = "instagram", days: int = 90) -> list[dict]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
    con = _conn()
    rows = con.execute(
        "SELECT * FROM daily_metrics WHERE platform=? AND date>=? ORDER BY date", (platform, cutoff)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


# ── Demographics ──────────────────────────────────────────────────────────────

def _upsert_demo(table: str, platform: str, rows: list[dict]):
    con = _conn()
    with con:
        con.execute(f"DELETE FROM {table} WHERE platform=?", (platform,))
        for r in rows:
            con.execute(
                f"INSERT OR REPLACE INTO {table} (bucket, platform, pct, count) VALUES (?,?,?,?)",
                (r.get("bucket") or r.get("label") or r.get("dimension", ""), platform,
                 r.get("percentage") or r.get("pct", 0),
                 r.get("count", 0)),
            )
    con.close()


def upsert_demographics(platform: str, data: dict):
    age = data.get("age") or data.get("age_ranges") or []
    gender = data.get("gender") or data.get("genders") or []
    country = data.get("country") or data.get("countries") or []
    city = data.get("city") or data.get("cities") or []
    if age:
        _upsert_demo("demographics_age", platform, age)
    if gender:
        _upsert_demo("demographics_gender", platform, gender)
    if country:
        _upsert_demo("demographics_country", platform, country)
    if city:
        _upsert_demo("demographics_city", platform, city)


def get_demographics(platform: str = "instagram") -> dict:
    con = _conn()
    result = {}
    for dim in ("age", "gender", "country", "city"):
        rows = con.execute(
            f"SELECT * FROM demographics_{dim} WHERE platform=? ORDER BY pct DESC", (platform,)
        ).fetchall()
        result[dim] = [dict(r) for r in rows]
    con.close()
    return result


# ── Posts ─────────────────────────────────────────────────────────────────────

def upsert_posts(platform: str, posts: list[dict]):
    con = _conn()
    with con:
        for p in posts:
            post_id = p.get("id") or p.get("post_id") or p.get("_id", "")
            if not post_id:
                continue
            con.execute("""
                INSERT OR REPLACE INTO posts
                (id, platform, caption, media_type, permalink, thumbnail, timestamp,
                 likes, comments, saves, shares, reach, views, engagement, raw_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                post_id, platform,
                p.get("content") or p.get("caption", ""),
                p.get("media_type") or p.get("type", ""),
                p.get("permalink") or p.get("url", ""),
                p.get("picture") or p.get("thumbnail_url") or p.get("thumbnail") or p.get("media_url", ""),
                p.get("createdTime") or p.get("timestamp") or p.get("created_at") or p.get("published_at", ""),
                p.get("likeCount") or p.get("like_count") or p.get("likes", 0),
                p.get("commentCount") or p.get("comments_count") or p.get("comments", 0),
                p.get("saved") or p.get("saves", 0),
                p.get("shares", 0),
                p.get("reach", 0),
                p.get("views", 0) or p.get("video_views", 0) or p.get("view_count", 0),
                p.get("engagement_rate") or p.get("engagement", 0),
                json.dumps(p),
            ))
    con.close()


def get_posts(platform: str = None, limit: int = 200) -> list[dict]:
    con = _conn()
    if platform:
        rows = con.execute(
            "SELECT * FROM posts WHERE platform=? ORDER BY timestamp DESC LIMIT ?", (platform, limit)
        ).fetchall()
    else:
        rows = con.execute(
            "SELECT * FROM posts ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
    con.close()
    return [dict(r) for r in rows]


# ── Comments ──────────────────────────────────────────────────────────────────

def upsert_comments(platform: str, comments: list[dict]):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
    con = _conn()
    with con:
        con.execute("DELETE FROM comments WHERE platform=? AND timestamp<?", (platform, cutoff))
        for c in comments:
            cid = c.get("id") or c.get("comment_id") or c.get("_id", "")
            if not cid:
                continue
            con.execute("""
                INSERT OR REPLACE INTO comments
                (id, post_id, platform, username, text, timestamp, likes, raw_json)
                VALUES (?,?,?,?,?,?,?,?)
            """, (
                cid,
                c.get("post_id") or c.get("media_id", ""),
                platform,
                c.get("username") or c.get("from", {}).get("username", "") if isinstance(c.get("from"), dict) else c.get("username", ""),
                c.get("text") or c.get("message", ""),
                c.get("timestamp") or c.get("created_at", ""),
                c.get("like_count") or c.get("likes", 0),
                json.dumps(c),
            ))
    con.close()


def get_comments(platform: str = None, post_id: str = None, limit: int = 500) -> list[dict]:
    con = _conn()
    query = "SELECT * FROM comments WHERE 1=1"
    params = []
    if platform:
        query += " AND platform=?"
        params.append(platform)
    if post_id:
        query += " AND post_id=?"
        params.append(post_id)
    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)
    rows = con.execute(query, params).fetchall()
    con.close()
    return [dict(r) for r in rows]


# ── Conversations & Messages ──────────────────────────────────────────────────

def upsert_conversations(conversations: list[dict]):
    con = _conn()
    with con:
        for c in conversations:
            cid = c.get("id") or c.get("_id", "")
            if not cid:
                continue
            con.execute("""
                INSERT OR REPLACE INTO conversations (id, platform, username, updated_at, raw_json)
                VALUES (?,?,?,?,?)
            """, (
                cid, "instagram",
                c.get("username") or c.get("participants", [{}])[0].get("username", "") if c.get("participants") else c.get("username", ""),
                c.get("updated_time") or c.get("updated_at", ""),
                json.dumps(c),
            ))
    con.close()


def upsert_messages(conversation_id: str, messages: list[dict]):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    con = _conn()
    with con:
        con.execute(
            "DELETE FROM messages WHERE conversation_id=? AND timestamp<?",
            (conversation_id, cutoff),
        )
        for m in messages:
            mid = m.get("id") or m.get("_id", "")
            if not mid:
                continue
            from_val = m.get("from") or {}
            from_user = from_val.get("username") or from_val.get("name", "") if isinstance(from_val, dict) else str(from_val)
            con.execute("""
                INSERT OR REPLACE INTO messages
                (id, conversation_id, platform, from_user, text, timestamp, raw_json)
                VALUES (?,?,?,?,?,?,?)
            """, (
                mid, conversation_id, "instagram",
                from_user,
                m.get("message") or m.get("text", ""),
                m.get("created_time") or m.get("timestamp", ""),
                json.dumps(m),
            ))
    con.close()


def get_messages(limit: int = 200) -> list[dict]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    con = _conn()
    rows = con.execute(
        "SELECT * FROM messages WHERE timestamp>=? ORDER BY timestamp DESC LIMIT ?",
        (cutoff, limit),
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


# ── Best time ─────────────────────────────────────────────────────────────────

def upsert_best_time(platform: str, rows: list[dict]):
    con = _conn()
    with con:
        con.execute("DELETE FROM best_time WHERE platform=?", (platform,))
        for r in rows:
            con.execute("""
                INSERT OR REPLACE INTO best_time (day_of_week, hour, platform, score)
                VALUES (?,?,?,?)
            """, (
                r.get("day_of_week") or r.get("day", 0),
                r.get("hour", 0),
                platform,
                r.get("score") or r.get("engagement_score") or r.get("avg_engagement", 0),
            ))
    con.close()


def get_best_time(platform: str = "instagram") -> list[dict]:
    con = _conn()
    rows = con.execute("SELECT * FROM best_time WHERE platform=?", (platform,)).fetchall()
    con.close()
    return [dict(r) for r in rows]


# ── Posting frequency & content decay ────────────────────────────────────────

def upsert_posting_frequency(platform: str, rows: list[dict]):
    con = _conn()
    with con:
        con.execute("DELETE FROM posting_frequency WHERE platform=?", (platform,))
        for r in rows:
            con.execute("""
                INSERT OR REPLACE INTO posting_frequency (posts_per_week, platform, avg_engagement, raw_json)
                VALUES (?,?,?,?)
            """, (
                r.get("posts_per_week") or r.get("frequency", 0),
                platform,
                r.get("avg_engagement") or r.get("engagement", 0),
                json.dumps(r),
            ))
    con.close()


def upsert_content_decay(platform: str, rows: list[dict]):
    con = _conn()
    with con:
        con.execute("DELETE FROM content_decay WHERE platform=?", (platform,))
        for i, r in enumerate(rows):
            con.execute("""
                INSERT OR REPLACE INTO content_decay (bucket_order, platform, label, avg_reach, avg_likes, raw_json)
                VALUES (?,?,?,?,?,?)
            """, (
                r.get("bucket_order", i),
                platform,
                r.get("label") or r.get("bucket", ""),
                r.get("avg_reach", 0),
                r.get("avg_likes", 0),
                json.dumps(r),
            ))
    con.close()


# ── Follower history ──────────────────────────────────────────────────────────

def upsert_follower_history(platform: str, rows: list[dict]):
    con = _conn()
    with con:
        for r in rows:
            con.execute("""
                INSERT OR REPLACE INTO follower_history (date, platform, followers, gained, lost)
                VALUES (?,?,?,?,?)
            """, (
                r.get("date", ""),
                platform,
                r.get("followers") or r.get("follower_count", 0),
                r.get("gained") or r.get("followers_gained", 0),
                r.get("lost") or r.get("followers_lost", 0),
            ))
    con.close()


def get_follower_history(platform: str = "instagram", days: int = 90) -> list[dict]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
    con = _conn()
    rows = con.execute(
        "SELECT * FROM follower_history WHERE platform=? AND date>=? ORDER BY date", (platform, cutoff)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


# ── Ideas ─────────────────────────────────────────────────────────────────────

def save_ideas(ideas: list[dict], batch_id: str):
    con = _conn()
    with con:
        for idea in ideas:
            con.execute("""
                INSERT INTO ideas
                (generated_at, batch_id, source_bucket, platforms, angle, format, rationale,
                 basis_post_ids, basis_comment_ids, basis_message_ids,
                 evidence_quotes, why_good_idea, suggested_angle, discarded)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,0)
            """, (
                datetime.now(timezone.utc).isoformat(),
                batch_id,
                idea.get("source_bucket", "top_content"),
                json.dumps(idea.get("platforms", [])),
                idea.get("angle", ""),
                idea.get("format", ""),
                idea.get("rationale", ""),
                json.dumps(idea.get("basis_post_ids", [])),
                json.dumps(idea.get("basis_comment_ids", [])),
                json.dumps(idea.get("basis_message_ids", [])),
                json.dumps(idea.get("evidence_quotes", [])),
                idea.get("why_good_idea", ""),
                idea.get("suggested_angle", ""),
            ))
    con.close()


def get_active_ideas(platform: str = None, batch_id: str = None) -> list[dict]:
    con = _conn()
    query = "SELECT * FROM ideas WHERE discarded=0"
    params = []
    if platform:
        query += " AND platforms LIKE ?"
        params.append(f'%"{platform}"%')
    if batch_id:
        query += " AND batch_id=?"
        params.append(batch_id)
    query += " ORDER BY id DESC"
    rows = con.execute(query, params).fetchall()
    con.close()
    result = []
    for r in rows:
        d = dict(r)
        for f in ("platforms", "basis_post_ids", "basis_comment_ids", "basis_message_ids", "evidence_quotes"):
            try:
                d[f] = json.loads(d[f] or "[]")
            except Exception:
                d[f] = []
        result.append(d)
    return result


def discard_idea(idea_id: int, angle: str, source_bucket: str, platform: str, reason_quick: str, reason_text: str = ""):
    con = _conn()
    with con:
        con.execute("UPDATE ideas SET discarded=1 WHERE id=?", (idea_id,))
        con.execute("""
            INSERT INTO idea_discards (idea_id, angle, source_bucket, platform, discarded_at, reason_quick, reason_text)
            VALUES (?,?,?,?,?,?,?)
        """, (
            idea_id, angle, source_bucket, platform,
            datetime.now(timezone.utc).isoformat(),
            reason_quick, reason_text,
        ))
    con.close()


def get_recent_discards(limit: int = 50) -> list[dict]:
    con = _conn()
    rows = con.execute(
        "SELECT * FROM idea_discards ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


# ── Refresh log ───────────────────────────────────────────────────────────────

def log_refresh_start() -> int:
    con = _conn()
    with con:
        cur = con.execute(
            "INSERT INTO refresh_log (started_at, status) VALUES (?,?)",
            (datetime.now(timezone.utc).isoformat(), "running"),
        )
        rid = cur.lastrowid
    con.close()
    return rid


def log_refresh_end(rid: int, status: str = "ok", error: str = ""):
    con = _conn()
    with con:
        con.execute(
            "UPDATE refresh_log SET ended_at=?, status=?, error=? WHERE id=?",
            (datetime.now(timezone.utc).isoformat(), status, error, rid),
        )
    con.close()


def get_last_refresh() -> dict | None:
    con = _conn()
    row = con.execute("SELECT * FROM refresh_log ORDER BY id DESC LIMIT 1").fetchone()
    con.close()
    return dict(row) if row else None
