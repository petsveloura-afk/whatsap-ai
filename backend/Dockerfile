FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt . 
RUN pip install --no-cache-dir -r requirements.txt
COPY app app
COPY migrations migrations
COPY alembic.ini .
RUN useradd --create-home --uid 10001 app && chown -R app:app /app
USER app
ENV WORKER_ENABLED=1
CMD ["sh","-c","alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
