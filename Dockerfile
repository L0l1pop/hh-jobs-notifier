FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Системные зависимости при необходимости
RUN apt-get update && apt-get install -y --no-install-recommends build-essential gcc && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Важно: копируем весь проект в /app
COPY . /app

# Опционально: добавить /app в PYTHONPATH (подстраховка)
ENV PYTHONPATH="/app:${PYTHONPATH}"

CMD ["python", "bot/main.py"]
