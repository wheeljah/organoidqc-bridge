# =============================================
# OrganoidQC Bridge — Dockerfile
# 클라우드 배포 (Railway / Render)
# 분석 우선순위: OrganoID subprocess → pixel → stub
# =============================================

FROM python:3.11-slim

# 시스템 의존성
RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Python 의존성 설치 ─────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
 && pip install --no-cache-dir tensorflow-cpu==2.16.1

# ── OrganoID 설치 (픽셀 수준 세그멘테이션) ─
RUN apt-get update && apt-get install -y --no-install-recommends wget \
 && rm -rf /var/lib/apt/lists/* \
 && wget -qO- https://github.com/jbuckman/OrganoID/archive/refs/heads/main.tar.gz \
        | tar xz -C /tmp \
 && mv /tmp/OrganoID-main /app/organoID \
 && if [ -f /app/organoID/requirements.txt ]; then \
        pip install --no-cache-dir -r /app/organoID/requirements.txt; \
    fi

# ── 앱 소스 복사 ──────────────────────────
COPY app/ app/
COPY run.py .
COPY OrganoidQC_v3_8.html .

# 업로드 임시 디렉터리 (컨테이너 재시작 시 초기화됨)
RUN mkdir -p /tmp/uploads

ENV ORGANO_ID_DIR=/app/organoID \
    UPLOAD_DIR=/tmp/uploads \
    HOST=0.0.0.0 \
    PORT=8000 \
    KEEP_UPLOADS=false \
    PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["python", "run.py"]
