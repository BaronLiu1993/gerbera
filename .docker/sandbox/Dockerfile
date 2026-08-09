FROM python:3.12-slim

COPY .docker/sandbox/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

USER 10001:10001

WORKDIR /workspace
