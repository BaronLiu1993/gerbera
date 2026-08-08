FROM python:3.12-slim

RUN pip install --no-cache-dir \
    numpy \
    pandas \
    scipy

USER 10001:10001

WORKDIR /workspace
