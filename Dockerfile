FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir $(python3 -c "import tomllib,pathlib; print(' '.join(tomllib.loads(pathlib.Path('pyproject.toml').read_text())['project']['dependencies']))")
COPY . .
CMD uvicorn seo_saas.server:app --host 0.0.0.0 --port ${PORT:-8000}
