FROM python:3.9-alpine

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Устанавливаем системные зависимости для сборки Python-пакетов
RUN apk add --no-cache \
    gcc \
    musl-dev \
    libffi-dev \
    openssl-dev \
    make

# Копируем файл зависимостей и устанавливаем Python-пакеты
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Создаём непривилегированного пользователя
RUN adduser -D appuser

# Создаём тестовый лог-файл и каталог для БД
RUN mkdir -p /app/data && \
    touch /var/log/auth.log && \
    chown -R appuser:appuser /app /var/log/auth.log

# Копируем код приложения
COPY --chown=appuser:appuser . .

# Переключаемся на непривилегированного пользователя
USER appuser

# По умолчанию используем тестовый лог внутри контейнера
ENV LOG_FILE_PATH=/var/log/auth.log

# Открываем порт 5000
EXPOSE 5000

# Команда запуска
CMD ["python", "app.py"]