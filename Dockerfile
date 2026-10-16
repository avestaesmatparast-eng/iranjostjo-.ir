FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY . .

# Hugging Face Spaces روی پورت 7860 گوش می‌دهد
ENV PORT=7860
EXPOSE 7860
CMD ["sh", "-c", "gunicorn -b 0.0.0.0:${PORT} -w 2 --threads 4 -t 120 app:app"]
