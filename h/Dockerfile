"""
Dockerfile للـ ONEMT Bot
يشتغل على VPS بدون محاكي بدون Frida

الإعداد:
  1. على جهازك (Windows مع المحاكي):
     python extract_session_adb.py --save-all
     
  2. على VPS:
     docker build -t onemt-bot .
     docker run -v $(pwd)/session_cache.json:/app/session_cache.json \
                -v $(pwd)/onemt_bot.log:/app/onemt_bot.log \
                onemt-bot --email "user@mail.com" --password "any"

  3. تشغيل متعدد الحسابات:
     docker-compose up -d
"""

FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir requests pycryptodome

COPY onemt_bot.py .

# session_cache.json يُضاف كـ volume من الخارج
VOLUME ["/app/session_cache.json", "/app/onemt_bot.log"]

ENTRYPOINT ["python", "onemt_bot.py"]
