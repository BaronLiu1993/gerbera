FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY . /app/gerbera_harness
ENV PYTHONPATH=/app
EXPOSE 8000
CMD ["uvicorn", "gerbera_harness.server.server:app", "--host", "0.0.0.0", "--port", "8000"]
