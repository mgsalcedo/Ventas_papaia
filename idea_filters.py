import re

ADORATION_PATTERNS = [
    r"\bte amo+\b", r"\bte adoro\b", r"\bte admiro\b",
    r"\beres mi (?:[íi]dola|[íi]dolo|favorita?)\b",
    r"\beres (?:mi |la |un |una )?(?:diosa?|reina?|reinota|favorita?|m[aá]xima?|crack|grande|inspiraci[óo]n)\b",
    r"\bdios[ae]\b", r"\breina\b", r"\breinota\b",
    r"\bpreciosa\b", r"\bhermosa\b", r"\blinda+\b", r"\blindo+\b",
    r"\bbonita\b", r"\bbonito\b", r"\bbella\b", r"\bdivina\b",
    r"\bbrutal\b", r"\bespectacular\b", r"\bfabulosa?\b",
    r"\bgenial\b", r"\bincre[ií]ble\b", r"\bperfecta?\b",
    r"\bmaravillosa?\b", r"\bbuen[íi]sim[ao]\b", r"\bbrav[oa]\b",
    r"\bfelicit\w*\b", r"\bfelicidades\b", r"\bgracias\b",
    r"\bque (?:linda|lindo|hermosa|preciosa|bella|bonita|chimba|chimbita|genia)\b",
    r"\bqu[eé] (?:linda|lindo|hermosa|preciosa|bella|bonita|chimba|chimbita|genia)\b",
    r"\bla (?:mejor|m[aá]xima|m[aá]s|number one)\b",
    r"\beres la mejor\b", r"\bsublim\w*\b", r"\bidola\b",
    r"\b[íi]dola\b", r"\b[íi]dolo\b", r"\bbb+\b",
    r"\b(?:hola|holi|holaa+)\b",
    r"\bi love (?:it|you|this)\b", r"\blove (?:it|you|this)\b",
    r"\bamazing\b", r"\bgorgeous\b", r"\bbeautiful\b",
    r"\bawesome\b", r"\bperfect\b", r"\bqueen\b",
    r"\bstunning\b", r"\bso cute\b", r"\byes\b", r"\bwow\b", r"\bomg\b",
    r"\bjajaja+\b", r"\bjeje+\b", r"\bjiji+\b", r"\bguau+\b",
    r"\bayyy+\b", r"\baaa+\b", r"\bsii+\b", r"\bs[íi]\b",
    r"\bclaro\b", r"\bok+\b", r"\bcierto\b", r"\btotal\b",
    r"\beso es\b", r"\bmuy bien\b", r"\bsuper\b", r"\bs[uú]per\b",
    r"\btal cual\b", r"\bexacto\b",
]

BOT_PATTERNS = [
    # GENÉRICAS — funcionan para cualquier creadora
    r"\bhaz cl[ií]ck? aqu[ií]\b",
    r"\bhaz clic aqu[ií]\b",
    r"\bd[eé]jame contarte\b",
    r"\bte prepar[eé]\b",
    r"\bnunca hab[ií]a compartido\b",
    r"\bes mi programa m[aá]s\b",
    r"\bmi programa m[aá]s completo\b",
    r"\bes mi curso m[aá]s\b",
    r"\baprende(?:r[aá]s|s) (?:todo|de cero)\b",
    r"\bcuando quieras acceder\b",
    r"\baccede al curso\b",
    r"\bcurso gratuito\b",
    r"\bnos vemos ah[ií]\b",
    r"\bestoy por aqu[ií]\b",
    r"\bsolo me quiero asegurar\b",
    r"\bme quiero asegurar de que\b",
    r"\bperfecto!? para tener acceso\b",
    r"\bperfecto!? ahora s[oó]?lo voy a necesitar\b",
    r"\bahora s[oó]lo voy a necesitar\b",
    r"\bveo en mi sistema\b",
    r"\bya tengo tu (?:correo|email|nombre)\b",
    r"\best[aá]s en l[ií]nea\b",
    r"\bescr[ií]belo abajo\b",
    r"\bconsiste en \d+ correos?\b",
    r"\bcada correo est[aá] dise[ñn]ado\b",
    r"\bes la misma estrategia que us[eé]\b",
    r"\bun gusto tenerte por aqu[ií]\b",
    r"\bya eres de la casa\b",
    r"\baqu[ií] lo tienes+\b",
    r"\bs[ií]i+ por aqu[ií]\b",
    r"\bun gusto saludarte+\b",
    r"\bqu[eé] lindo verte\b",
    r"\bsi quieres acceso\b",
    r"\bdale clic\b",
    r"\bhaz clic\b",
    # ESPECÍFICAS — agrega aquí el nombre de tu chatbot / programas / cursos
    # Ejemplo: r"\bRuperta\b", r"\bCash Content\b"
]

URL_RE = re.compile(r"https?://\S+")
EMAIL_ONLY_RE = re.compile(r"^\s*[\w.+-]+@[\w-]+\.[\w.-]+\s*$")
EMOJI_PUNCT_RE = re.compile(
    r"^[\s\U0001F300-\U0001FAFF\U00002600-\U000027BF"
    r"\U0001F900-\U0001F9FF -⁯✀-➿"
    r"!?.,;:¡¿\-_*&%$#@+<>=~`'^|\\/'\"()\[\]{}]+$",
    re.UNICODE,
)

_ADORATION_RES = [re.compile(p, re.IGNORECASE) for p in ADORATION_PATTERNS]
_BOT_RES = [re.compile(p, re.IGNORECASE) for p in BOT_PATTERNS]


def _strip_adoration(text: str) -> str:
    for r in _ADORATION_RES:
        text = r.sub(" ", text)
    return text.strip()


def is_likely_bot_message(text: str) -> bool:
    if not text:
        return True
    for r in _BOT_RES:
        if r.search(text):
            return True
    # URL-only or email-only
    if EMAIL_ONLY_RE.match(text):
        return True
    text_without_urls = URL_RE.sub("", text).strip()
    if len(text_without_urls) < 20 and URL_RE.search(text):
        return True
    return False


def is_substantive_comment(text: str, min_len: int = 20) -> bool:
    if not text or not text.strip():
        return False
    if EMOJI_PUNCT_RE.match(text.strip()):
        return False
    # Keep if has question mark (strong signal)
    if "?" in text or "¿" in text:
        return True
    stripped = _strip_adoration(text)
    return len(stripped) >= min_len


def is_substantive_dm(text: str, min_len: int = 15) -> bool:
    if not text or not text.strip():
        return False
    if is_likely_bot_message(text):
        return False
    if EMOJI_PUNCT_RE.match(text.strip()):
        return False
    if "?" in text or "¿" in text:
        return True
    stripped = _strip_adoration(text)
    return len(stripped) >= min_len


def filter_comments(comments: list[dict]) -> list[dict]:
    return [c for c in comments if is_substantive_comment(c.get("text") or c.get("message", ""))]


def filter_messages(messages: list[dict]) -> list[dict]:
    return [m for m in messages if is_substantive_dm(m.get("text") or m.get("message", ""))]
