FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY logs ./logs
COPY config/docker.yaml ./config/docker.yaml
COPY run_avatar_server.py ./

EXPOSE 8000

CMD ["python", "run_avatar_server.py", "--env", "docker"]
