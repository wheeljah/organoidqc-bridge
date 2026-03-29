# =============================================
# main.py — OrganoidQC Bridge API
#
# 엔드포인트:
#   GET  /           → OrganoidQC 웹 앱 HTML 서빙 (연구자용)
#   GET  /health     → 상태 + 모델 로드 여부
#   POST /analyze    → 이미지 업로드 → 분석 결과 JSON
#   GET  /images     → 저장된 이미지 목록
#   GET  /images/{filename} → 저장된 이미지 반환
# =============================================
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.config import (
    BASE_DIR, CORS_ORIGINS, MAX_IMAGE_SIZE_MB, ALLOWED_EXTENSIONS,
    UPLOAD_DIR, ORGANO_ID_DIR,
)
from app.schemas import AnalyzeResponse, HealthResponse
from app.analyzer import (
    analyze_image, load_organoID_model,
    is_model_loaded, is_organoID_dir_ok,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("main")

BRIDGE_VERSION = "0.3.0-step3"


# ── 서버 시작/종료 훅 ─────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=== OrganoidQC Bridge 서버 시작 ===")
    ok = load_organoID_model()
    if is_organoID_dir_ok():
        logger.info(f"OrganoID subprocess 모드 활성 (dir={ORGANO_ID_DIR})")
    elif ok:
        logger.info("OrganoID TFLite 직접 로드 완료")
    else:
        logger.warning("OrganoID 미설치 → pixel / stub 분석 모드")
    yield
    logger.info("=== 서버 종료 ===")


# ── FastAPI 앱 ────────────────────────────────
app = FastAPI(
    title="OrganoidQC Bridge",
    description=(
        "OrganoidQC 웹 앱과 OrganoID 분석 엔진을 연결하는 로컬 REST API.\n\n"
        "**분석 모드 우선순위:** organoID > pixel > stub"
    ),
    version=BRIDGE_VERSION,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# uploads 폴더를 정적 파일로 서빙 (이미지 미리보기용)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")


# ── 라우트 ────────────────────────────────────

@app.get("/", response_class=HTMLResponse, tags=["general"])
def root():
    """
    OrganoidQC 웹 앱 서빙.
    연구자는 이 URL 하나만 열면 됩니다.
    HTML 파일 경로: 프로젝트 루트의 OrganoidQC_v5_2.html
    """
    html_path = BASE_DIR / "OrganoidQC_v5_2.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
    # HTML 파일이 없을 경우 JSON fallback
    from fastapi.responses import JSONResponse
    return JSONResponse({
        "service": "OrganoidQC Bridge",
        "version": BRIDGE_VERSION,
        "error":   "OrganoidQC_v5_2.html 파일을 찾을 수 없습니다.",
        "docs":    "/docs",
    })


@app.get("/info", tags=["general"])
def info():
    """서버 상태 JSON (디버그용)"""
    return {
        "service": "OrganoidQC Bridge",
        "version": BRIDGE_VERSION,
        "docs":    "/docs",
        "health":  "/health",
        "mode":    "organoID" if is_organoID_dir_ok() else
                   ("tflite" if is_model_loaded() else "pixel/stub"),
    }


@app.get("/health", response_model=HealthResponse, tags=["general"])
def health():
    """서버 상태 및 OrganoID 환경 확인"""
    return HealthResponse(
        status           = "ok",
        organoID_loaded  = is_model_loaded(),
        organoID_dir_ok  = is_organoID_dir_ok(),
        version          = BRIDGE_VERSION,
    )


@app.post("/analyze", response_model=AnalyzeResponse, tags=["analysis"])
async def analyze(file: UploadFile = File(...)):
    """
    현미경 이미지를 업로드하면 QC 지표 JSON을 반환합니다.

    - 지원 형식: JPG, PNG, TIF, TIFF
    - 최대 크기: 20 MB
    - OrganoID 설치 시: 세그멘테이션 기반 분석
    - 미설치 시: OpenCV 픽셀 분석 → stub 순으로 fallback
    """
    # 1) 확장자 검사
    suffix = "." + (file.filename or "upload.png").rsplit(".", 1)[-1].lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"지원하지 않는 파일 형식: {suffix}. 허용: {sorted(ALLOWED_EXTENSIONS)}",
        )

    # 2) 크기 검사
    image_bytes = await file.read()
    max_bytes   = MAX_IMAGE_SIZE_MB * 1024 * 1024
    if len(image_bytes) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"파일 초과 ({len(image_bytes)//1024//1024}MB). 최대 {MAX_IMAGE_SIZE_MB}MB",
        )

    # 3) 분석
    try:
        result = analyze_image(image_bytes, original_filename=file.filename or "upload.png")
    except ValueError as e:
        return AnalyzeResponse(success=False, error=str(e))
    except Exception as e:
        logger.exception("분석 중 예외 발생")
        return AnalyzeResponse(success=False, error=f"분석 실패: {e}")

    return AnalyzeResponse(
        success=True,
        result=result,
        filename=file.filename,
    )


@app.get("/images", tags=["storage"])
def list_images():
    """uploads/ 에 저장된 이미지 목록 반환"""
    files = []
    for f in sorted(UPLOAD_DIR.iterdir()):
        if f.suffix.lower() in ALLOWED_EXTENSIONS:
            files.append({
                "filename": f.name,
                "size_kb":  round(f.stat().st_size / 1024, 1),
                "url":      f"/uploads/{f.name}",
            })
    return {"count": len(files), "images": files}
