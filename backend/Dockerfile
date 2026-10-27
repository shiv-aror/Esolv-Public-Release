FROM python:3.12-slim
WORKDIR /srv
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
COPY pyproject.toml ./
COPY app ./app
RUN pip install .

ENV DATA_DIR=/srv/data
RUN mkdir -p /srv/data/models && python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5', cache_dir='/srv/data/models')"
COPY data/docs ./data/docs
COPY data/accommodations.sample.csv ./data/
EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/health')"
CMD ["sh", "-c", "python -m app.rag.ingest && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
