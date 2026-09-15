FROM python:3.9-alpine

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Системные зависимости
RUN apk add --no-cache curl gcc musl-dev libffi-dev openssl-dev

# Устанавливаем uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && cp /root/.local/bin/uv /usr/local/bin/uv \
    && cp /root/.local/bin/uvx /usr/local/bin/uvx \
    && chmod +x /usr/local/bin/uv /usr/local/bin/uvx \
    && uv --version

# Копируем файлы зависимостей отдельно (кэш)
COPY pyproject.toml uv.lock ./

# Устанавливаем зависимости строго по uv.lock
RUN uv sync --frozen --no-dev --no-install-project

# Копируем код
COPY . .

# Пользователь и права
RUN adduser -D appuser \
    && mkdir -p /app/data \
    && touch /var/log/auth.log \
    && chown -R appuser /app /var/log/auth.log

USER appuser

EXPOSE 5000

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]