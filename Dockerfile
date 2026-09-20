FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY src /app/src
COPY config /app/config
ENV PYTHONPATH=/app/src
ENV QUICKBOOKS_ENV=sandbox
ENV QBO_BIND=0.0.0.0
ENV QBO_PORT=14112
EXPOSE 14112
CMD ["sh", "-c", "uvicorn hermes_qbo.app:app --host ${QBO_BIND:-127.0.0.1} --port ${QBO_PORT:-14112}"]
