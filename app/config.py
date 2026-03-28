# =============================================
# config.py — 서버 전역 설정
# 클라우드 배포 대응 버전
# =============================================
import os
from pathlib import Path

# 프로젝트 루트
BASE_DIR = Path(__file__).parent.parent

# ── 업로드 디렉터리 ───────────────────────────
# 클라우드: UPLOAD_DIR=/tmp/uploads  (컨테이너 재시작 시 초기화)
# 로컬:    UPLOAD_DIR=./uploads
_upload_dir_env = os.getenv("UPLOAD_DIR", str(BASE_DIR / "uploads"))
UPLOAD_DIR = Path(_upload_dir_env)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ── OrganoID 경로 ─────────────────────────────
# 클라우드 Docker: /app/organoID (Dockerfile에서 clone)
# 로컬:           ./organoID (setup_organoID.sh 실행 후)
ORGANO_ID_DIR = Path(os.getenv("ORGANO_ID_DIR", str(BASE_DIR / "organoID")))

# OrganoID 모델 경로
MODEL_DIR = BASE_DIR / "models"
MODEL_DIR.mkdir(exist_ok=True)
ORGANO_ID_MODEL = Path(os.getenv(
    "ORGANO_ID_MODEL",
    str(ORGANO_ID_DIR / "TrainedModels" / "TissueFCN_512.tflite")
))

# ── 분석 설정 ────────────────────────────────
MAX_IMAGE_SIZE_MB = int(os.getenv("MAX_IMAGE_SIZE_MB", "20"))
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}

# 이미지 전처리
PREPROCESS_TARGET_SIZE = (512, 512)
CLAHE_CLIP_LIMIT = 2.0

# 이미지 저장 여부
# 클라우드 기본값: False (임시 스토리지)
KEEP_UPLOADS = os.getenv("KEEP_UPLOADS", "false").lower() in ("true", "1", "yes")

# ── CORS ────────────────────────────────────
# 클라우드 배포: 와일드카드(*) 또는 ALLOWED_ORIGINS 환경변수로 제한
_origins_env = os.getenv("ALLOWED_ORIGINS", "")
if _origins_env:
    CORS_ORIGINS = [o.strip() for o in _origins_env.split(",") if o.strip()]
else:
    # 기본: 모든 오리진 허용 (로컬 file:// + 클라우드 모두 대응)
    CORS_ORIGINS = ["*"]

# ── 서버 ─────────────────────────────────────
HOST = os.getenv("HOST", "0.0.0.0")
# Railway / Render는 PORT 환경변수를 자동으로 주입
PORT = int(os.getenv("PORT", "8000"))
