#!/usr/bin/env bash
# =============================================
# setup_organoID.sh — OrganoID 설치 스크립트
#
# 사용법:
#   chmod +x setup_organoID.sh
#   ./setup_organoID.sh
#
# 이 스크립트가 수행하는 작업:
#   1) OrganoID GitHub 레포 클론
#   2) 필요 Python 패키지 설치
#   3) 사전 학습 모델 다운로드 (있을 경우)
# =============================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORGANO_DIR="$SCRIPT_DIR/organoID"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  OrganoidQC Bridge — OrganoID 설치"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── 1) OrganoID 클론 ──────────────────────────
if [ -d "$ORGANO_DIR/.git" ]; then
    echo "✅ OrganoID 레포 이미 존재 → git pull"
    cd "$ORGANO_DIR" && git pull
else
    echo "📥 OrganoID 클론 중..."
    git clone https://github.com/jbuckman/OrganoID.git "$ORGANO_DIR"
fi

# ── 2) Python 패키지 설치 ─────────────────────
echo ""
echo "📦 Python 의존성 설치..."
pip install \
    tensorflow-cpu==2.16.1 \
    scipy==1.13.0           \
    scikit-image==0.23.2    \
    opencv-python-headless==4.9.0.80 \
    pillow==10.3.0          \
    numpy==1.26.4

# ── 3) OrganoID 자체 requirements 설치 ──────
if [ -f "$ORGANO_DIR/requirements.txt" ]; then
    echo ""
    echo "📦 OrganoID requirements.txt 설치..."
    pip install -r "$ORGANO_DIR/requirements.txt"
fi

# ── 4) 모델 파일 확인 ─────────────────────────
echo ""
echo "🔍 사전학습 모델 파일 확인..."
MODELS_DIR="$ORGANO_DIR/TrainedModels"
if [ -d "$MODELS_DIR" ]; then
    echo "✅ TrainedModels 폴더 존재:"
    ls "$MODELS_DIR"
else
    echo "⚠️  TrainedModels 폴더 없음."
    echo "   OrganoID 레포에서 직접 모델 파일을 다운받거나,"
    echo "   OrganoID README를 참고하여 모델을 준비하세요."
    echo "   → https://github.com/jbuckman/OrganoID#trained-models"
fi

# ── 5) 환경변수 안내 ──────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ 설치 완료!"
echo ""
echo "서버 시작:"
echo "  export ORGANO_ID_DIR=\"$ORGANO_DIR\""
echo "  python run.py"
echo ""
echo "또는 .env 파일에 추가:"
echo "  ORGANO_ID_DIR=$ORGANO_DIR"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
