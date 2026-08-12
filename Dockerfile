FROM python:3.9-alpine

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apk add --no-cache curl gcc musl-dev libffi-dev openssl-dev

# Установка uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && cp /root/.local/bin/uv /usr/local/bin/uv \
    && chmod +x /usr/local/bin/uv \
    && uv --version

COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

RUN adduser -D appuser \
    && mkdir -p /app/data \
    && touch /var/log/auth.log \
    && chown -R appuser /app /var/log/auth.log

USER appuser

COPY --chown=appuser . .

EXPOSE 5000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5000"]