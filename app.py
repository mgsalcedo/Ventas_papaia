import os
import re
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv(override=True)

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

import cache
import ideas as ideas_module

TZ = ZoneInfo(os.getenv("DASHBOARD_TZ", "America/Lima"))

_ID_PATTERN_LONG = re.compile(r"\b(post|comment|message)[\s_-]?id[:\s]*\d+\b", re.IGNORECASE)
_ID_PATTERN_LABELED = re.compile(r"\b(post|comment|message)\s+\d{10,}\b", re.IGNORECASE)
_ID_PATTERN_BARE = re.compile(r"\b\d{12,}\b")

st.set_page_config(page_title="Dashboard de Contenido", layout="wide", page_icon="📊")

cache.init_db()


def _strip_ids(text: str) -> str:
    if not text:
        return ""
    text = _ID_PATTERN_LONG.sub(lambda m: m.group(1), text)
    text = _ID_PATTERN_LABELED.sub(lambda m: m.group(1), text)
    text = _ID_PATTERN_BARE.sub("", text)
    return text


def _fmt_num(n) -> str:
    if n is None:
        return "—"
    n = int(n)
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


def _last_refresh_str() -> str:
    r = cache.get_last_refresh()
    if not r or not r.get("ended_at"):
        return "Nunca"
    try:
        dt = datetime.fromisoformat(r["ended_at"]).astimezone(TZ)
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return r.get("ended_at", "—")


# ── Header ───────────────────────────────────────────────────────────────────

def render_header():
    snap_ig = cache.get_account_snapshot("instagram")
    health_ig = cache.get_health("instagram")

    col_ig, col_refresh = st.columns([3, 1])

    with col_ig:
        if snap_ig:
            pic = snap_ig.get("profile_pic", "")
            username = snap_ig.get("username", "—")
            followers = snap_ig.get("followers", 0)

            health_color = "🟢"
            if health_ig:
                status = health_ig.get("status", "").lower()
                if "warn" in status or "yellow" in status:
                    health_color = "🟡"
                elif "error" in status or "red" in status or "bad" in status:
                    health_color = "🔴"

            row = st.columns([0.08, 0.92])
            if pic:
                try:
                    row[0].image(pic, width=55)
                except Exception:
                    row[0].write("📷")
            row[1].markdown(
                f"**@{username}** · {_fmt_num(followers)} seguidores {health_color}  \n"
                f"*Última actualización: {_last_refresh_str()}*"
            )
        else:
            st.info("Aún no hay datos. Corre `python refresh.py` primero.")

    with col_refresh:
        if st.button("🔄 Refrescar datos", type="primary"):
            with st.spinner("Descargando datos de Zernio... (~30s)"):
                try:
                    import refresh as refresh_module
                    refresh_module.run()
                    st.success("¡Datos actualizados!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al refrescar: {e}")

    st.divider()


# ── Platform selector ─────────────────────────────────────────────────────────

def platform_selector() -> str:
    snap_yt = cache.get_account_snapshot("youtube")
    options = ["Instagram"]
    if snap_yt:
        options += ["YouTube", "Ambas"]
    selected = st.radio("Plataforma:", options, horizontal=True, key="platform_selector")
    return selected.lower()


# ── Tab 1: Resumen ────────────────────────────────────────────────────────────

def tab_resumen(platform: str):
    st.subheader("📊 Resumen — últimos 30 días")

    if platform in ("instagram", "ambas"):
        ins = cache.get_insights_30d("instagram")
        if ins:
            st.markdown("#### Instagram")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Alcance", _fmt_num(ins.get("reach")))
            c2.metric("Vistas", _fmt_num(ins.get("views") or ins.get("impressions")))
            c3.metric("Usuarios enganchados", _fmt_num(ins.get("engaged")))
            c4.metric("Interacciones", _fmt_num(ins.get("interactions")))
            c5, c6, c7, c8 = st.columns(4)
            c5.metric("Likes", _fmt_num(ins.get("likes")))
            c6.metric("Comentarios", _fmt_num(ins.get("comments")))
            c7.metric("Guardados", _fmt_num(ins.get("saves")))
            c8.metric("Compartidos", _fmt_num(ins.get("shares")))
        else:
            st.warning("No hay datos de insights para Instagram. Corre el refresh.")

    if platform in ("youtube", "ambas"):
        yt_totals = cache.get_insights_30d("youtube")
        if yt_totals:
            st.markdown("#### YouTube")
            c1, c2, c3 = st.columns(3)
            c1.metric("Vistas", _fmt_num(yt_totals.get("views")))
            c2.metric("Horas de reproducción", _fmt_num(yt_totals.get("watch_hours")))
            c3.metric("Subs neto", _fmt_num(yt_totals.get("engaged")))


# ── Tab 2: Tendencia ──────────────────────────────────────────────────────────

def tab_tendencia(platform: str):
    st.subheader("📈 Tendencia — últimos 90 días")

    platforms_to_show = []
    if platform in ("instagram", "ambas"):
        platforms_to_show.append("instagram")
    if platform in ("youtube", "ambas"):
        platforms_to_show.append("youtube")

    all_rows = []
    for p in platforms_to_show:
        rows = cache.get_daily_metrics(p, days=90)
        for r in rows:
            r["platform_label"] = p.capitalize()
        all_rows.extend(rows)

    if not all_rows:
        st.warning("No hay métricas diarias. Corre el refresh.")
        return

    df = pd.DataFrame(all_rows)
    df["date"] = pd.to_datetime(df["date"])

    metric_options = [c for c in ["reach", "views", "likes", "comments", "saves", "shares", "followers", "engaged"] if c in df.columns]
    selected_metrics = st.multiselect("Métricas a mostrar:", metric_options, default=["reach", "likes"] if "reach" in metric_options else metric_options[:2])

    for m in selected_metrics:
        fig = px.line(df, x="date", y=m, color="platform_label", title=m.capitalize(),
                      labels={"date": "Fecha", m: m.capitalize(), "platform_label": "Plataforma"})
        st.plotly_chart(fig, use_container_width=True)

    fh_ig = cache.get_follower_history("instagram", days=90)
    if fh_ig:
        df_fh = pd.DataFrame(fh_ig)
        df_fh["date"] = pd.to_datetime(df_fh["date"])
        fig_fh = px.line(df_fh, x="date", y="followers", title="Crecimiento de seguidores IG",
                         labels={"date": "Fecha", "followers": "Seguidores"})
        st.plotly_chart(fig_fh, use_container_width=True)


# ── Tab 3: Audiencia ──────────────────────────────────────────────────────────

def tab_audiencia(platform: str):
    st.subheader("👥 Demografía de audiencia")

    platforms_to_show = []
    if platform in ("instagram", "ambas"):
        platforms_to_show.append("instagram")
    if platform in ("youtube", "ambas"):
        platforms_to_show.append("youtube")

    for p in platforms_to_show:
        demo = cache.get_demographics(p)
        st.markdown(f"#### {p.capitalize()}")
        tabs = st.tabs(["Edad", "Género", "Países", "Ciudades"] if p == "instagram" else ["Edad", "Género", "Países"])

        dims = ["age", "gender", "country"] + (["city"] if p == "instagram" else [])
        for tab, dim in zip(tabs, dims):
            with tab:
                data = demo.get(dim, [])
                if data:
                    df = pd.DataFrame(data)
                    if "pct" in df.columns:
                        fig = px.bar(df, x="bucket", y="pct",
                                     labels={"bucket": dim.capitalize(), "pct": "% audiencia"},
                                     title=f"{dim.capitalize()} — {p.capitalize()}")
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.dataframe(df)
                else:
                    st.info(f"Sin datos de {dim} para {p}.")


# ── Tab 4: Posts ──────────────────────────────────────────────────────────────

def tab_posts(platform: str):
    st.subheader("📝 Posts por performance")

    platforms_to_show = []
    if platform in ("instagram", "ambas"):
        platforms_to_show.append("instagram")
    if platform in ("youtube", "ambas"):
        platforms_to_show.append("youtube")

    posts = []
    for p in platforms_to_show:
        for post in cache.get_posts(p, limit=100):
            post["platform_label"] = p.capitalize()
            posts.append(post)

    if not posts:
        st.warning("No hay posts en el cache. Corre el refresh.")
        return

    sort_by = st.selectbox("Ordenar por:", ["likes", "comments", "saves", "shares", "reach", "views"])
    posts_sorted = sorted(posts, key=lambda p: p.get(sort_by) or 0, reverse=True)

    cols_per_row = 3
    for i in range(0, min(len(posts_sorted), 30), cols_per_row):
        cols = st.columns(cols_per_row)
        for j, col in enumerate(cols):
            if i + j >= len(posts_sorted):
                break
            post = posts_sorted[i + j]
            with col:
                thumb = post.get("thumbnail", "")
                if thumb:
                    try:
                        st.image(thumb, use_column_width=True)
                    except Exception:
                        st.write("🖼️")
                badge = "📷 IG" if post.get("platform_label", "").lower() == "instagram" else "▶️ YT"
                caption = (post.get("caption") or "")[:80]
                st.caption(f"{badge} | ❤️ {_fmt_num(post.get('likes'))} 💬 {_fmt_num(post.get('comments'))}")
                st.caption(caption)
                permalink = post.get("permalink", "")
                if permalink:
                    st.markdown(f"[Ver post]({permalink})")
                if st.button(f"💬 Ver comentarios", key=f"comments_{post.get('id', i+j)}"):
                    st.session_state[f"show_comments_{post.get('id')}"] = True

                if st.session_state.get(f"show_comments_{post.get('id')}"):
                    comments = cache.get_comments(post_id=post.get("id", ""), limit=50)
                    if comments:
                        with st.expander(f"Comentarios ({len(comments)})", expanded=True):
                            for c in comments:
                                st.markdown(f"**@{c.get('username', '?')}**: {c.get('text', '')}")
                    else:
                        st.info("No hay comentarios cacheados para este post.")


# ── Tab 5: Cuándo publicar ────────────────────────────────────────────────────

def tab_cuando_publicar(platform: str):
    st.subheader("🕐 Mejor hora para publicar")

    platforms_to_show = []
    if platform in ("instagram", "ambas"):
        platforms_to_show.append("instagram")
    if platform in ("youtube", "ambas"):
        platforms_to_show.append("youtube")

    for p in platforms_to_show:
        bt_data = cache.get_best_time(p)
        if not bt_data:
            st.info(f"No hay datos de mejor hora para {p}. Corre el refresh.")
            continue

        st.markdown(f"#### {p.capitalize()} (hora en {os.getenv('DASHBOARD_TZ', 'America/Lima')})")
        df = pd.DataFrame(bt_data)

        day_names = {0: "Lun", 1: "Mar", 2: "Mié", 3: "Jue", 4: "Vie", 5: "Sáb", 6: "Dom"}
        df["day_name"] = df["day_of_week"].map(day_names)

        pivot = df.pivot_table(index="hour", columns="day_name", values="score", aggfunc="mean")
        # Reorder columns
        ordered_cols = [d for d in ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"] if d in pivot.columns]
        pivot = pivot[ordered_cols]

        fig = px.imshow(
            pivot,
            labels={"x": "Día", "y": "Hora (local)", "color": "Score"},
            title=f"Heatmap engagement {p.capitalize()}",
            color_continuous_scale="YlOrRd",
            aspect="auto",
        )
        st.plotly_chart(fig, use_container_width=True)


# ── Tab 6: Frecuencia ─────────────────────────────────────────────────────────

def tab_frecuencia(platform: str):
    st.subheader("📅 Frecuencia de publicación")

    platforms_to_show = []
    if platform in ("instagram", "ambas"):
        platforms_to_show.append("instagram")
    if platform in ("youtube", "ambas"):
        platforms_to_show.append("youtube")

    all_freq = []
    for p in platforms_to_show:
        con = cache._conn()
        rows = con.execute("SELECT * FROM posting_frequency WHERE platform=?", (p,)).fetchall()
        con.close()
        for r in rows:
            d = dict(r)
            d["platform_label"] = p.capitalize()
            all_freq.append(d)

    if all_freq:
        df = pd.DataFrame(all_freq)
        if "posts_per_week" in df.columns and "avg_engagement" in df.columns:
            fig = px.scatter(
                df, x="posts_per_week", y="avg_engagement", color="platform_label",
                title="Posts por semana vs Engagement promedio",
                labels={"posts_per_week": "Posts/semana", "avg_engagement": "Engagement promedio", "platform_label": "Plataforma"},
            )
            st.plotly_chart(fig, use_container_width=True)

    # Content decay
    st.markdown("#### Decaimiento de contenido")
    for p in platforms_to_show:
        con = cache._conn()
        rows = con.execute("SELECT * FROM content_decay WHERE platform=? ORDER BY bucket_order", (p,)).fetchall()
        con.close()
        if rows:
            df_decay = pd.DataFrame([dict(r) for r in rows])
            fig = px.bar(df_decay, x="label", y="avg_likes",
                         title=f"Engagement por antigüedad del post — {p.capitalize()}",
                         labels={"label": "Periodo", "avg_likes": "Likes promedio"})
            st.plotly_chart(fig, use_container_width=True)


# ── Tab 7: Ideas ──────────────────────────────────────────────────────────────

def tab_ideas():
    st.subheader("💡 Ideas de contenido")

    snap_yt = cache.get_account_snapshot("youtube")
    platform_opts = ["Instagram"] + (["YouTube"] if snap_yt else [])
    selected_platform = st.radio("Plataforma:", platform_opts, horizontal=True, key="ideas_platform")
    platform_key = selected_platform.lower()

    cost_hint = "~$0.10-0.30 por generación completa"
    if st.button(f"✨ Generar todas las ideas de {selected_platform}", help=cost_hint):
        with st.spinner(f"Claude está analizando tu contenido... (~15-30s)  {cost_hint}"):
            try:
                if platform_key == "instagram":
                    new_ideas, batch_id = ideas_module.generate_all_ideas_ig()
                else:
                    new_ideas, batch_id = ideas_module.generate_all_ideas_yt()
                st.session_state["last_batch_id"] = batch_id
                st.success(f"✅ {len(new_ideas)} ideas generadas")
                st.rerun()
            except Exception as e:
                st.error(f"Error al generar ideas: {e}")

    # Load active ideas
    active_ideas = cache.get_active_ideas(platform=platform_key)

    if not active_ideas:
        st.info("Aún no hay ideas. Haz click en el botón de arriba para generar.")
        return

    # Group by bucket
    buckets = {}
    for idea in active_ideas:
        b = idea.get("source_bucket", "top_content")
        buckets.setdefault(b, []).append(idea)

    bucket_config = {
        "comments": ("💬 De comentarios", "instagram" if platform_key == "instagram" else "youtube"),
        "dms": ("📩 De DMs (solo IG)", "instagram"),
        "top_content": ("🏆 De contenido top", platform_key),
    }

    for bucket_key, (bucket_label, bucket_platform) in bucket_config.items():
        ideas_in_bucket = buckets.get(bucket_key, [])
        if bucket_key == "dms" and platform_key != "instagram":
            continue

        with st.expander(f"{bucket_label} — {len(ideas_in_bucket)} ideas", expanded=True):
            regen_col1, _ = st.columns([1, 3])
            with regen_col1:
                if st.button(f"🔄 Regenerar {bucket_label}", key=f"regen_{bucket_key}_{platform_key}"):
                    with st.spinner("Regenerando..."):
                        try:
                            _, batch_id = ideas_module.generate_bucket(bucket_platform, bucket_key)
                            st.session_state["last_batch_id"] = batch_id
                            st.success("✅ Regenerado")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")

            if not ideas_in_bucket:
                st.info("No hay ideas en este bucket.")
                continue

            for idea in ideas_in_bucket:
                _render_idea_card(idea)

    # Discards history
    discards = cache.get_recent_discards(10)
    if discards:
        with st.expander("🗑️ Últimos descartes (Claude los lee al regenerar)", expanded=False):
            for d in discards:
                st.markdown(f"- **{d.get('source_bucket')}** — \"{d.get('angle', '')}\" → _{d.get('reason_quick', '')}_")


def _render_idea_card(idea: dict):
    idea_id = idea.get("id")
    angle = _strip_ids(idea.get("angle", "Sin título"))
    fmt = idea.get("format", "")
    evidence = idea.get("evidence_quotes") or []
    why = _strip_ids(idea.get("why_good_idea", ""))
    suggested = _strip_ids(idea.get("suggested_angle", ""))
    permalink_map = {p.get("id"): p.get("permalink") for p in cache.get_posts(limit=200)}

    with st.container(border=True):
        col_title, col_fmt = st.columns([4, 1])
        col_title.markdown(f"**{angle}**")
        if fmt:
            col_fmt.code(fmt)

        if evidence:
            st.markdown("**Comentarios / Lo que la inspiró:**")
            for q in evidence:
                st.markdown(f"> {_strip_ids(q)}")

        if why:
            st.markdown("**¿Por qué es buena idea?**")
            st.markdown(why)

        if suggested:
            st.markdown("**Ángulo sugerido:**")
            st.markdown(suggested)

        # Post links
        post_ids = idea.get("basis_post_ids") or []
        links = [f"[post]({permalink_map[pid]})" for pid in post_ids if pid in permalink_map and permalink_map[pid]]
        if links:
            st.caption("Posts relacionados: " + " · ".join(links))

        # Discard button
        if st.button(f"✕ Descartar idea", key=f"discard_{idea_id}"):
            st.session_state[f"discard_modal_{idea_id}"] = True

        if st.session_state.get(f"discard_modal_{idea_id}"):
            with st.form(key=f"discard_form_{idea_id}"):
                st.markdown("**¿Por qué descartás esta idea?**")
                reason_quick = st.radio(
                    "Razón:",
                    ["Tema ya cubierto", "No me interesa", "Muy básica", "No es mi estilo", "Otro"],
                    key=f"reason_{idea_id}",
                )
                reason_text = st.text_input("Detalles (opcional):", key=f"reason_text_{idea_id}")
                c1, c2 = st.columns(2)
                submitted = c1.form_submit_button("Confirmar descarte", type="primary")
                cancelled = c2.form_submit_button("Cancelar")

                if submitted:
                    cache.discard_idea(
                        idea_id=idea_id,
                        angle=idea.get("angle", ""),
                        source_bucket=idea.get("source_bucket", ""),
                        platform=json.dumps(idea.get("platforms") or []),
                        reason_quick=reason_quick,
                        reason_text=reason_text,
                    )
                    st.session_state.pop(f"discard_modal_{idea_id}", None)
                    st.rerun()
                if cancelled:
                    st.session_state.pop(f"discard_modal_{idea_id}", None)
                    st.rerun()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    render_header()
    platform = platform_selector()
    st.divider()

    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "📊 Resumen", "📈 Tendencia", "👥 Audiencia",
        "📝 Posts", "🕐 Cuándo publicar", "📅 Frecuencia", "💡 Ideas",
    ])

    with tab1:
        tab_resumen(platform)
    with tab2:
        tab_tendencia(platform)
    with tab3:
        tab_audiencia(platform)
    with tab4:
        tab_posts(platform)
    with tab5:
        tab_cuando_publicar(platform)
    with tab6:
        tab_frecuencia(platform)
    with tab7:
        tab_ideas()


if __name__ == "__main__":
    main()
