import asyncio
import os
import threading
import time
from collections import defaultdict, deque

from flask import Flask, Response, jsonify, render_template, request

import core

# قالب HTML کنار همین فایل‌ها قرار دارد
app = Flask(__name__, template_folder=".")

TTS_VOICE = "fa-IR-DilaraNeural"   # صدای فارسی زن؛ برای صدای مرد: fa-IR-FaridNeural
TTS_MAX_CHARS = 1500
SEARCH_LIMIT_PER_MIN = 12          # هر آدرس IP در دقیقه
TTS_LIMIT_PER_MIN = 20

# ---- محدودیت ساده‌ی تعداد درخواست (برای وقتی سایت عمومی است) ----
_hits = defaultdict(deque)
_lock = threading.Lock()


def _client_ip() -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    return (forwarded.split(",")[0].strip() or request.remote_addr or "?")


def _limited(kind: str, limit: int, window: int = 60) -> bool:
    now = time.time()
    key = (kind, _client_ip())
    with _lock:
        q = _hits[key]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            return True
        q.append(now)
        if len(_hits) > 5000:  # پاک‌سازی ورودی‌های قدیمی تا حافظه پر نشود
            for k in [k for k, v in _hits.items() if not v or now - v[-1] > window]:
                del _hits[k]
    return False


@app.route("/")
def index():
    query = request.args.get("q", "").strip()
    if not query:
        return render_template("index.html", query="", result=None)
    if _limited("search", SEARCH_LIMIT_PER_MIN):
        result = {
            "query": query, "overall": "", "sources": [], "videos": [],
            "notes": ["تعداد جستجوها در این یک دقیقه زیاد بود؛ کمی صبر کنید و دوباره امتحان کنید."],
        }
    else:
        result = core.run(query[:300])
    return render_template("index.html", query=query, result=result)


async def _synthesize(text: str) -> bytes:
    import edge_tts  # صدای فارسی رایگان و بدون کلید (از سرویس Edge)

    chunks = []
    async for part in edge_tts.Communicate(text, TTS_VOICE).stream():
        if part["type"] == "audio":
            chunks.append(part["data"])
    return b"".join(chunks)


@app.post("/tts")
def tts():
    """متن فارسی را به فایل صوتی mp3 تبدیل می‌کند (برای دستگاه‌هایی که صدای فارسی ندارند)."""
    if _limited("tts", TTS_LIMIT_PER_MIN):
        return jsonify(error="rate_limited"), 429
    data = request.get_json(silent=True) or {}
    text = str(data.get("text", "")).strip()[:TTS_MAX_CHARS]
    if not text:
        return jsonify(error="empty"), 400
    try:
        audio = asyncio.run(_synthesize(text))
        if not audio:
            raise RuntimeError("no audio")
        return Response(audio, mimetype="audio/mpeg")
    except Exception:
        return jsonify(error="tts_failed"), 503


if __name__ == "__main__":
    # روی کامپیوتر خودتان: فقط 127.0.0.1:5000. روی سرور (Docker) از HOST و PORT خوانده می‌شود.
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "5000")), debug=False)
