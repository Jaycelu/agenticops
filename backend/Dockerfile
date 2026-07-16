FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore

WORKDIR /app

RUN set -e; \
    apt-get update >/tmp/apt-install.log 2>&1; \
    apt-get install -y --no-install-recommends build-essential libffi-dev libssl-dev libxml2-dev libxmlsec1-dev libxmlsec1-openssl pkg-config >>/tmp/apt-install.log 2>&1; \
    rm -rf /var/lib/apt/lists/* /tmp/apt-install.log

COPY requirements.txt constraints.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
