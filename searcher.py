"""جستجوی وب (DuckDuckGo، رایگان و بدون کلید API) و دریافت متن صفحه‌ها."""
import re
from itertools import zip_longest

import requests
from bs4 import BeautifulSoup

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
MAX_PAGE_BYTES = 1_500_000
MAX_TEXT_CHARS = 20_000


def has_persian(text: str) -> bool:
    return bool(re.search(r"[\u0600-\u06FF]", text))


def _ddgs_class():
    # بسته‌ی جدید «ddgs» است؛ نام قدیمی آن «duckduckgo_search» بود.
    try:
        from ddgs import DDGS
    except ImportError:  # pragma: no cover
        from duckduckgo_search import DDGS
    return DDGS


def _translate_to_english(query: str) -> str | None:
    try:
        from deep_translator import GoogleTranslator

        en = GoogleTranslator(source="fa", target="en").translate(query)
        if en and en.strip().lower() != query.strip().lower():
            return en.strip()
    except Exception:
        pass
    return None


def search_web(query: str, max_results: int = 6):
    """برمی‌گرداند: (نتایج, عبارت‌های جستجوشده, پیام خطا یا None).

    اگر سؤال فارسی باشد، ترجمه‌ی انگلیسی آن هم جستجو می‌شود تا
    منابع بین‌المللی هم پوشش داده شوند.
    """
    queries = [query]
    if has_persian(query):
        en = _translate_to_english(query)
        if en:
            queries.append(en)

    DDGS = _ddgs_class()
    per_query, error = [], None
    for q in queries:
        try:
            items = list(DDGS().text(q, max_results=max_results))
        except Exception as exc:  # شبکه، محدودیت نرخ و ...
            items, error = [], str(exc)
        per_query.append(items)

    results, seen = [], set()
    for group in zip_longest(*per_query):  # ترکیب نوبتی نتایج دو جستجو
        for item in group:
            if not item:
                continue
            url = item.get("href") or item.get("url")
            if not url or not url.startswith(("http://", "https://")) or url in seen:
                continue
            seen.add(url)
            results.append(
                {
                    "title": item.get("title") or url,
                    "url": url,
                    "snippet": item.get("body") or "",
                }
            )
    return results[:max_results], queries, (error if not results else None)


def fetch_text(url: str, timeout: int = 8) -> str:
    """متن اصلی صفحه (پاراگراف‌ها) را برمی‌گرداند؛ در صورت خطا رشته‌ی خالی."""
    try:
        # with: اتصال همیشه بسته می‌شود (قبلاً باز می‌ماند و منابع هدر می‌رفت)
        with requests.get(
            url, headers={"User-Agent": USER_AGENT}, timeout=timeout, stream=True
        ) as resp:
            ctype = resp.headers.get("Content-Type", "")
            if resp.status_code != 200 or "html" not in ctype.lower():
                return ""
            content = resp.raw.read(MAX_PAGE_BYTES, decode_content=True)
        soup = BeautifulSoup(content, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "aside", "header", "form"]):
            tag.decompose()
        paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        text = "\n".join(p for p in paragraphs if len(p) > 40)
        return text[:MAX_TEXT_CHARS]
    except Exception:
        return ""


# فقط پخش‌کننده‌ی یوتیوب داخل صفحه جاسازی می‌شود؛ بقیه‌ی منابع فقط لینک می‌شوند
ALLOWED_EMBED = (
    "https://www.youtube.com/embed/",
    "https://www.youtube-nocookie.com/embed/",
)


def search_videos(queries, max_results: int = 6):
    """ویدیوهای مرتبط را از DuckDuckGo می‌گیرد (رایگان، بدون کلید). در خطا لیست خالی."""
    try:
        DDGS = _ddgs_class()
    except Exception:
        return []
    per_query = []
    for q in list(queries)[:2]:
        try:
            per_query.append(list(DDGS().videos(q, max_results=max_results)))
        except Exception:
            per_query.append([])

    out, seen = [], set()
    for group in zip_longest(*per_query):  # ترکیب نوبتی نتایج دو جستجو
        for item in group:
            if not item:
                continue
            url = item.get("content") or ""
            if not url.startswith(("http://", "https://")) or url in seen:
                continue
            seen.add(url)
            images = item.get("images") or {}
            thumb = images.get("medium") or images.get("large") or images.get("small") or ""
            if not str(thumb).startswith("https://"):
                thumb = ""
            embed = item.get("embed_url") or ""
            if not str(embed).startswith(ALLOWED_EMBED):
                embed = ""
            out.append(
                {
                    "title": item.get("title") or url,
                    "url": url,
                    "thumb": thumb,
                    "embed": embed,
                    "duration": item.get("duration") or "",
                    "publisher": item.get("uploader") or item.get("publisher") or "",
                }
            )
    return out[:max_results]
