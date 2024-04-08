FROM python:3.11.9-slim
# FROM python:3-slim AS builder

ADD . /app
WORKDIR /app

# We are installing a dependency here directly into our app source dir
# RUN pip install --target=/app requests

# # A distroless container image with Python and some basics like SSL certificates
# # https://github.com/GoogleContainerTools/distroless
# FROM gcr.io/distroless/python3-debian10
# COPY --from=builder /app /app
# WORKDIR /app
ENV PYTHONPATH /app

RUN apt-get update && apt-get install --no-install-recommends --yes git gh

RUN chmod +x /app/main.py

VOLUME [ "/app/tests" ]

CMD ["/app/main.py"]