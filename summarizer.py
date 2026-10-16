"""خلاصه‌سازی استخراجی (بدون هوش مصنوعی پولی) و ترجمه‌ی رایگان به فارسی."""
import math
import re
from collections import Counter

STOPWORDS = set(
    """a an the and or but if then else of to in on at by for with about as into like
    through after over between out against during without before under around among is
    are was were be been being have has had do does did will would can could should may
    might must this that these those it its i you he she we they them his her our their
    my your me him us what which who whom whose when where why how not no nor so than too
    very just also from up down off again further once here there all any both each few
    more most other some such only own same
    و در به از که این را با است برای آن یک هم کرد شد می های ها بود تا یا اما اگر بر
    نیز هر دو خود آنها ما من تو او شده شود باشد کند کنند""".split()
)

_SENT_SPLIT = re.compile(r"(?<=[.!?؟۔])\s+|\n+")
_WORD = re.compile(r"\w+", re.UNICODE)


def _words(text: str):
    return [w.lower() for w in _WORD.findall(text)]


def query_terms(queries) -> set:
    terms = set()
    for q in queries:
        terms |= {w for w in _words(q) if w not in STOPWORDS and len(w) > 2}
    return terms


def split_sentences(text: str):
    sentences = [s.strip() for s in _SENT_SPLIT.split(text)]
    return [s for s in sentences if 40 <= len(s) <= 400]


def summarize(text: str, terms: set, n: int = 3):
    """n جمله‌ی مهم را به ترتیب ظهور در متن برمی‌گرداند.

    خروجی: (لیست جمله‌ها, اندیس بهترین جمله در همان لیست).
    امتیاز = فراوانی کلمات + شباهت به کلمات سؤال.
    """
    sentences = split_sentences(text)
    if not sentences:
        return [], 0

    freq = Counter(w for w in _words(text) if w not in STOPWORDS and len(w) > 2)
    scored = []
    for idx, sent in enumerate(sentences):
        words = [w for w in _words(sent) if w not in STOPWORDS and len(w) > 2]
        if not words:
            continue
        base = sum(freq[w] for w in words) / math.sqrt(len(words))
        overlap = len(terms & set(words))
        scored.append((base + 5 * overlap * math.log1p(max(freq.values())), idx))

    if not scored:
        return [], 0
    top = sorted(scored, reverse=True)[:n]
    best_original_idx = top[0][1]
    chosen = sorted(idx for _, idx in top)
    return [sentences[i] for i in chosen], chosen.index(best_original_idx)


def _chunks(text: str, size: int = 4000):
    chunk = ""
    for line in text.split("\n"):
        if len(chunk) + len(line) + 1 > size and chunk:
            yield chunk
            chunk = ""
        chunk += line + "\n"
    if chunk.strip():
        yield chunk


def to_persian(sentences):
    """لیست جمله‌ها را به فارسی ترجمه می‌کند. برمی‌گرداند: (جمله‌های فارسی, موفق؟)."""
    if not sentences:
        return [], True
    try:
        from deep_translator import GoogleTranslator

        translator = GoogleTranslator(source="auto", target="fa")
        joined = "\n".join(sentences)
        translated = "\n".join(translator.translate(c).strip() for c in _chunks(joined))
        parts = [p.strip() for p in translated.split("\n") if p.strip()]
        if len(parts) != len(sentences):  # اگر ترجمه خطوط را جابه‌جا کرد
            parts = [translated.replace("\n", " ")]
        return parts, True
    except Exception:
        return list(sentences), False
