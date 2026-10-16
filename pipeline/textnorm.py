"""Language detection, Persian normalisation and tokenisation shared by extract.py and analyze.py."""
import re
import unicodedata

ARABIC_SCRIPT = re.compile(r"[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")
LATIN = re.compile(r"[A-Za-z]")
# Letters (any script) optionally joined by ZWNJ, so Persian forms like «می‌شود» stay one token.
TOKEN_RE = re.compile(r"[^\W\d_](?:[^\W\d_]|‌)+", re.UNICODE)

_CHAR_MAP = str.maketrans({
    "ي": "ی", "ى": "ی", "ك": "ک", "ۀ": "هٔ", "ة": "ه",
    "ـ": "",                                   # tatweel (kashida)
    "‎": "", "‏": "", "‪": "", "‫": "", "‬": "",  # bidi marks
    " ": " ",
    **{chr(0x06F0 + i): str(i) for i in range(10)},  # Persian digits
    **{chr(0x0660 + i): str(i) for i in range(10)},  # Arabic digits
})
_DIACRITICS = re.compile(r"[ً-ٰٟ]")

PERSIAN_STOPWORDS = set("""
و در به از که این را با است برای آن یک خود تا کرد بر هم نیز شد شود کند ها های ای اما یا شده بود باید
دارد کرده داشت آنها او ما من تو شما ایشان هر همه چه چون اگر پس نه بی پیش بین روی زیر میان دیگر چند
کنند کنیم کردن کردند شدن شدند شوند بودن بوده بودند باشد باشند هست هستند نیست نبود دهد داد دادن گفت
گوید گفته وی آیا ولی اینکه آنکه چنین چنان همین همان هیچ البته حتی فقط تنها بسیار خیلی بیشتر کمتر
می نمی اند ام ایم اید اش شان مان تان یعنی زیرا چرا کجا کی چگونه همچنین سپس اکنون هنوز دیگری دیگران
می‌شود می‌کند می‌کنند می‌توان می‌باشد می‌شوند می‌دهد نمی‌شود است، دو سه اول باشد، طور مورد درباره
عنوان صورت جای بعد قبل هنگام زمان وقتی آنچه کسی چیزی جز مثل مانند نزد سوی طی ضمن بدون علاوه
""".split())


def normalize(text: str) -> str:
    """Unicode clean-up that is safe for English and fixes common Persian PDF artefacts:
    presentation-form glyphs, Arabic ي/ك, diacritics, tatweel, bidi marks, non-Latin digits."""
    text = unicodedata.normalize("NFKC", text)   # also maps presentation forms (FB50–FEFF) to letters
    text = text.translate(_CHAR_MAP)
    text = _DIACRITICS.sub("", text)
    # some fonts map medial lam to U+01C1 «ǁ» in their ToUnicode table
    text = re.sub(r"(?<=[\u0600-\u06FF])\u01c1|\u01c1(?=[\u0600-\u06FF])", "ل", text)
    text = re.sub(r"‌{2,}", "‌", text)
    text = re.sub(r" ?‌ ?", "‌", text)  # stray spaces around ZWNJ
    return text


def detect_language(text: str) -> str:
    """'fa', 'en', 'mixed' or 'unknown' from the share of Persian/Arabic vs Latin letters."""
    fa, en = len(ARABIC_SCRIPT.findall(text)), len(LATIN.findall(text))
    total = fa + en
    if total < 50:
        return "unknown"
    if fa / total > 0.8:
        return "fa"
    if en / total > 0.8:
        return "en"
    return "mixed"


def _stopword_hits(words: list[str]) -> int:
    return sum(w in PERSIAN_STOPWORDS for w in words)


def fix_visual_order(text: str) -> tuple[str, bool]:
    """Some PDFs store Persian in visual (left-to-right) order, so words come out reversed
    («زا» instead of «از»). If reversed words look far more Persian than the originals,
    reverse each line. Returns (text, was_fixed)."""
    words = [w for w in TOKEN_RE.findall(text) if ARABIC_SCRIPT.search(w)][:5000]
    if len(words) < 30:
        return text, False
    normal, reversed_ = _stopword_hits(words), _stopword_hits([w[::-1] for w in words])
    if reversed_ > max(2 * normal, 10):
        return "\n".join(line[::-1] for line in text.split("\n")), True
    return text, False


def tokens(text: str) -> list[str]:
    return [t.lower().strip("‌") for t in TOKEN_RE.findall(text)]
