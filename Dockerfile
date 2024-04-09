FROM python:3.11.9-slim
# FROM python:3-slim AS builder

ADD . /app
WORKDIR /app

RUN apt-get update && apt-get install --no-install-recommends --yes git gh

RUN pip install --target=/app PyYAML PyGithub

ENV PYTHONPATH /app

RUN chmod +x /app/main.py

CMD ["python3", "/app/main.py"]