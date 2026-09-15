FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /workspace

COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

# Source is bind-mounted by Compose for development. Keeping this image
# source-free means dependency changes are the only reason to rebuild it.
EXPOSE 8000

CMD ["python", "run.py"]
