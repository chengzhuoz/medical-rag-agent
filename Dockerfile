FROM docker.m.daocloud.io/library/python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get -o Acquire::Retries=3 -o Acquire::http::Timeout=30 update \
    && apt-get install -y --no-install-recommends build-essential libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && pip install --no-cache-dir torch==2.3.1 --index-url https://download.pytorch.org/whl/cpu \
    && pip install -r requirements.txt

COPY . .
RUN mkdir -p /app/data/uploads /app/data/vectorstore

EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py collectstatic --noinput && gunicorn ph_backend.wsgi:application --bind 0.0.0.0:8000 --workers ${WEB_CONCURRENCY:-2} --timeout ${GUNICORN_TIMEOUT:-120} --access-logfile -"]