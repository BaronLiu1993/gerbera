FROM python:3.12-slim
WORKDIR /app
COPY .docker/harness/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY src/gerbera_harness /app/gerbera_harness
COPY src/gerbera_protocol /app/gerbera_protocol
ENV PYTHONPATH=/app
EXPOSE 8000
CMD ["uvicorn", "gerbera_harness.bootstrap:create_server_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
