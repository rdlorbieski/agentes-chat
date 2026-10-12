FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DB_PATH=/app/data/conversas.db

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app.py ./
COPY chatbot/ chatbot/
COPY .streamlit/config.toml .streamlit/config.toml

# Usuário sem privilégios. A pasta data/ é onde fica o SQLite das conversas:
# no docker-compose ela é um volume, para sobreviver a cada deploy.
RUN useradd --create-home --uid 1000 chat \
    && mkdir -p /app/data \
    && chown -R chat:chat /app/data
USER chat

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health', timeout=4)"

CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
