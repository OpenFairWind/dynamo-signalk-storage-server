FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY app ./app
COPY run.py dynamo-signalk-storage-server.sh ./
RUN chmod 0755 dynamo-signalk-storage-server.sh

ENTRYPOINT ["./dynamo-signalk-storage-server.sh"]
CMD ["flask", "--app", "run:flask_app", "run", "--host", "0.0.0.0", "--port", "13387"]
