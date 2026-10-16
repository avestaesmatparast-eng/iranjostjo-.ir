"""خط لولهٔ اصلی: جستجو ← دریافت متن ← خلاصه‌سازی ← ترجمه به فارسی (+ ویدیوهای مرتبط)."""
from concurrent.futures import ThreadPoolExecutor

from searcher import fetch_text, search_videos, search_web
from summarizer import query_terms, summarize, to_persian


def _process(args):
    item, text, terms = args
    body = text if len(text) > 200 else f"{item['snippet']}\n{text}"
    sentences, best = summarize(body, terms, n=3)
    if not sentences and item["snippet"]:
        sentences, best = [item["snippet"]], 0
    fa, ok = to_persian(sentences)
    # اگر هیچ جمله‌ای نبود، fa خالی است؛ بدون این شرط IndexError می‌دهد
    key = fa[best] if fa and ok and len(fa) == len(sentences) else (fa[0] if fa else "")
    return {
        "title": item["title"],
        "url": item["url"],
        "summary": " ".join(fa),
        "key": key,
        "translated": ok,
    }


def run(query: str) -> dict:
    query = query.strip()
    results, used_queries, error = search_web(query)
    if not results:
        return {
            "query": query,
            "overall": "",
            "sources": [],
            "videos": [],
            "notes": [
                "جستجو انجام نشد (احتمالاً اینترنت قطع است، فیلترشکن لازم است، یا موتور جستجو "
                "موقتاً محدودیت گذاشته). چند دقیقه بعد دوباره امتحان کنید."
                if error
                else "نتیجه‌ای پیدا نشد؛ سؤال را کمی تغییر دهید."
            ],
        }

    terms = query_terms(used_queries)
    with ThreadPoolExecutor(max_workers=8) as pool:
        videos_future = pool.submit(search_videos, used_queries)  # همزمان با بقیه
        texts = list(pool.map(lambda r: fetch_text(r["url"]), results))
        sources = list(pool.map(_process, [(r, t, terms) for r, t in zip(results, texts)]))
        try:
            videos = videos_future.result(timeout=20)
        except Exception:
            videos = []

    sources = [s for s in sources if s["summary"]]
    notes = []
    if not sources:
        # قبلاً در این حالت صفحه کاملاً خالی و بدون هیچ پیامی نمایش داده می‌شد
        return {
            "query": query,
            "overall": "",
            "sources": [],
            "videos": videos,
            "notes": ["از صفحه‌های پیداشده متنی برای خلاصه کردن به دست نیامد؛ سؤال را تغییر دهید."],
        }
    if any(not s["translated"] for s in sources):
        notes.append(
            "ترجمه‌ی رایگان در دسترس نبود؛ بعضی خلاصه‌ها به زبان اصلی نمایش داده شده‌اند."
        )

    overall = " ".join(s["key"] for s in sources[:5] if s["key"])
    return {
        "query": query,
        "overall": overall,
        "sources": sources,
        "videos": videos,
        "notes": notes,
    }
