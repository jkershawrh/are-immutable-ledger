FROM python:3.11-slim

WORKDIR /app

COPY api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY sdks/python/ ./sdks/python/
COPY api/gateway.py ./api/gateway.py

USER 1001
EXPOSE 28099
ENV LEDGER_ENDPOINT=localhost:19292
ENV GATEWAY_PORT=28099
ENV GATEWAY_HOST=0.0.0.0
CMD ["python", "api/gateway.py"]
