# =============================================
# analyzer.py — 이미지 분석 레이어
#
# Step 2: OpenCV 기반 픽셀 분석 (연결 성분)
# Step 3: OrganoID subprocess 파이프라인 연결
# =============================================
import io
import csv
import json
import logging
import math
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Optional, List, Tuple

import cv2
import numpy as np
from PIL import Image

from app.schemas import OrganoIDResult, OrganoIDOrganoid
from app.config import (
    UPLOAD_DIR, ORGANO_ID_DIR, ORGANO_ID_MODEL, KEEP_UPLOADS,
    PREPROCESS_TARGET_SIZE, CLAHE_CLIP_LIMIT,
)

logger = logging.getLogger("analyzer")

# OrganoID 모델 로드 상태 플래그
_organoID_model   = None   # tflite interpreter (직접 로드 시)
_organoID_dir_ok  = False  # subprocess 경로 유효 여부


# ══════════════════════════════════════════════
# 모델 초기화
# ══════════════════════════════════════════════

def load_organoID_model(model_path: Optional[Path] = None) -> bool:
    """
    서버 시작 시 OrganoID 환경을 확인.
    우선순위:
      1) ORGANO_ID_DIR 내 OrganoID.py 존재 → subprocess 모드
      2) ORGANO_ID_MODEL .tflite 파일 존재 → tflite 직접 로드 (선택)
      3) 둘 다 없으면 → pixel 분석 모드로 fallback
    """
    global _organoID_model, _organoID_dir_ok

    # — subprocess 모드 확인 —
    organoID_script = ORGANO_ID_DIR / "OrganoID.py"
    if organoID_script.exists():
        _organoID_dir_ok = True
        logger.info(f"OrganoID 스크립트 확인: {organoID_script}")
        return True

    # — tflite 직접 로드 시도 —
    target = model_path or ORGANO_ID_MODEL
    if target.exists():
        try:
            import tflite_runtime.interpreter as tflite
            _organoID_model = tflite.Interpreter(model_path=str(target))
            _organoID_model.allocate_tensors()
            logger.info(f"TFLite 모델 로드 완료: {target}")
            return True
        except ImportError:
            logger.warning("tflite_runtime 미설치 → pixel 분석 모드")
        except Exception as e:
            logger.warning(f"TFLite 모델 로드 실패: {e}")

    logger.info("OrganoID 미설치 → pixel 분석 모드로 동작")
    return False


def is_model_loaded() -> bool:
    return _organoID_model is not None or _organoID_dir_ok


def is_organoID_dir_ok() -> bool:
    return _organoID_dir_ok


# ══════════════════════════════════════════════
# Step 2 — 전처리 유틸
# ══════════════════════════════════════════════

def _preprocess(img: Image.Image) -> np.ndarray:
    """
    PIL Image → 전처리된 그레이스케일 np.ndarray (uint8).
    - 채널 정규화
    - CLAHE 대비 향상
    - Gaussian 노이즈 제거
    """
    # 그레이스케일 변환
    gray = np.array(img.convert("L"), dtype=np.uint8)

    # CLAHE (Contrast Limited Adaptive Histogram Equalization)
    clahe = cv2.createCLAHE(clipLimit=CLAHE_CLIP_LIMIT, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    # Gaussian blur — 노이즈 제거
    blurred = cv2.GaussianBlur(enhanced, (3, 3), 0)

    return blurred


def _segment_connected_components(
    gray: np.ndarray,
    min_area: int = 80,
    max_area: Optional[int] = None,
) -> Tuple[np.ndarray, List[dict]]:
    """
    Otsu 이진화 + 연결 성분 분석으로 오가노이드 후보 검출.
    Returns: (labeled_mask, list of component stats)
    """
    h, w = gray.shape
    if max_area is None:
        max_area = (h * w) // 4   # 전체 이미지의 25% 이하

    # Otsu 이진화
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # 모폴로지 연산으로 노이즈 제거
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN,  kernel, iterations=1)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)

    # 연결 성분
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
        binary, connectivity=8
    )

    components = []
    for i in range(1, num_labels):   # 0은 배경
        area = int(stats[i, cv2.CC_STAT_AREA])
        if area < min_area or area > max_area:
            continue

        x = int(stats[i, cv2.CC_STAT_LEFT])
        y = int(stats[i, cv2.CC_STAT_TOP])
        bw = int(stats[i, cv2.CC_STAT_WIDTH])
        bh = int(stats[i, cv2.CC_STAT_HEIGHT])
        cx, cy = centroids[i]

        # 원형도 계산
        mask = (labels == i).astype(np.uint8) * 255
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        circularity = 0.0
        if contours:
            perimeter = cv2.arcLength(contours[0], True)
            if perimeter > 0:
                circularity = round(4 * math.pi * area / (perimeter ** 2), 4)
                circularity = min(circularity, 1.0)

        # 평균 밝기
        region = gray[y:y+bh, x:x+bw]
        mean_intensity = round(float(np.mean(region)), 2)

        components.append({
            "label":          i,
            "area_px":        area,
            "circularity":    circularity,
            "centroid_x":     round(float(cx), 1),
            "centroid_y":     round(float(cy), 1),
            "mean_intensity": mean_intensity,
            "bbox":           [x, y, bw, bh],
        })

    return labels, components


# ══════════════════════════════════════════════
# Step 2 — 픽셀 기반 분석
# ══════════════════════════════════════════════

def _pixel_analyze(img: Image.Image, saved_path: Optional[str] = None) -> OrganoIDResult:
    """
    OpenCV 연결 성분 기반 픽셀 분석.
    OrganoID보다 정확도는 낮지만 의존성 없이 동작.
    """
    arr = _preprocess(img)
    h, w = arr.shape
    _, components = _segment_connected_components(arr)

    if not components:
        # 검출 실패 → stub fallback
        return _stub_analyze(img, saved_path)

    areas         = [c["area_px"]     for c in components]
    circularities = [c["circularity"] for c in components]
    intensities   = [c["mean_intensity"] for c in components]

    n              = len(components)
    mean_area      = round(float(np.mean(areas)), 1)
    size_cv        = round(float(np.std(areas) / (np.mean(areas) + 1e-6) * 100), 2)
    mean_circ      = round(float(np.mean(circularities)), 3)
    viability      = round(min(99.0, float(np.mean(intensities)) / 255 * 120), 1)
    qc_score       = round(
        (1 - min(size_cv / 30, 1)) * 40
        + mean_circ * 30
        + (viability / 100) * 30,
        1
    )
    osi_pass = (size_cv < 10) and (viability >= 70)

    organoids = [
        OrganoIDOrganoid(
            id=idx + 1,
            area_px=c["area_px"],
            circularity=c["circularity"],
            centroid_x=c["centroid_x"],
            centroid_y=c["centroid_y"],
            mean_intensity=c["mean_intensity"],
            bbox=c["bbox"],
        )
        for idx, c in enumerate(components)
    ]

    channels = len(img.getbands())

    return OrganoIDResult(
        organoid_count=n,
        mean_area_px=mean_area,
        size_cv=size_cv,
        mean_circularity=mean_circ,
        viability_proxy=viability,
        qc_score=qc_score,
        osi_pass=osi_pass,
        organoids=organoids,
        image_width=w,
        image_height=h,
        image_channels=channels,
        saved_path=saved_path,
        analysis_mode="pixel",
    )


# ══════════════════════════════════════════════
# Step 1 — Stub 분석 (fallback)
# ══════════════════════════════════════════════

def _stub_analyze(img: Image.Image, saved_path: Optional[str] = None) -> OrganoIDResult:
    """밝기 기반 간이 분석 (연결 성분 실패 시 fallback)"""
    arr = np.array(img.convert("L"), dtype=np.float32)
    h, w = arr.shape

    threshold   = 180
    bright_mask = arr > threshold
    bright_ratio = bright_mask.sum() / arr.size

    organoid_count   = max(1, int(bright_ratio * 60))
    mean_area_px     = round(float(bright_mask.sum() / max(organoid_count, 1)), 1)
    pixel_vals       = arr[bright_mask] if bright_mask.any() else arr.flatten()
    size_cv          = round(float(np.std(pixel_vals) / (np.mean(pixel_vals) + 1e-6) * 100), 2)
    mean_circularity = round(min(0.99, 0.70 + bright_ratio * 0.25), 3)
    viability_proxy  = round(min(99.0, bright_ratio * 120), 1)
    qc_score         = round(
        (1 - min(size_cv / 30, 1)) * 40
        + mean_circularity * 30
        + (viability_proxy / 100) * 30, 1
    )
    osi_pass = (size_cv < 10) and (viability_proxy >= 70)

    return OrganoIDResult(
        organoid_count=organoid_count,
        mean_area_px=mean_area_px,
        size_cv=size_cv,
        mean_circularity=mean_circularity,
        viability_proxy=viability_proxy,
        qc_score=qc_score,
        osi_pass=osi_pass,
        image_width=w,
        image_height=h,
        image_channels=len(img.getbands()),
        saved_path=saved_path,
        analysis_mode="stub",
    )


# ══════════════════════════════════════════════
# Step 3 — OrganoID subprocess 파이프라인
# ══════════════════════════════════════════════

def _organoID_subprocess_analyze(
    img: Image.Image,
    saved_path: Optional[str] = None,
) -> OrganoIDResult:
    """
    OrganoID.py를 subprocess로 실행해 세그멘테이션 결과 CSV를 파싱.

    OrganoID CLI 사용법 (공식):
      python OrganoID.py detect \\
        --input  <image_path> \\
        --output <out_dir>    \\
        --model  <model.tflite>

    출력 CSV 컬럼 예시 (OrganoID v1.1):
      Organoid, Area, Circularity, Centroid_X, Centroid_Y, Mean_Intensity, ...
    """
    organoID_script = ORGANO_ID_DIR / "OrganoID.py"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_dir = Path(tmpdir)

        # 입력 이미지 임시 저장
        tmp_img = tmp_dir / "input.png"
        img.save(str(tmp_img))

        out_dir = tmp_dir / "output"
        out_dir.mkdir()

        cmd = [
            sys.executable,
            str(organoID_script),
            "detect",
            "--input",  str(tmp_img),
            "--output", str(out_dir),
            "--model",  str(ORGANO_ID_MODEL),
        ]

        logger.info(f"OrganoID 실행: {' '.join(cmd)}")

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,   # 2분 타임아웃
                cwd=str(ORGANO_ID_DIR),
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("OrganoID 분석 타임아웃 (2분)")

        if proc.returncode != 0:
            logger.error(f"OrganoID stderr: {proc.stderr}")
            raise RuntimeError(f"OrganoID 종료 코드 {proc.returncode}: {proc.stderr[:300]}")

        # CSV 파일 탐색
        csv_files = list(out_dir.glob("*.csv"))
        if not csv_files:
            raise RuntimeError("OrganoID 출력 CSV 없음 — 분석 실패")

        return _parse_organoID_csv(csv_files[0], img, saved_path)


def _parse_organoID_csv(
    csv_path: Path,
    img: Image.Image,
    saved_path: Optional[str] = None,
) -> OrganoIDResult:
    """OrganoID 출력 CSV → OrganoIDResult 변환"""
    organoids: List[OrganoIDOrganoid] = []
    areas, circularities, intensities = [], [], []

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        # OrganoID 컬럼명 정규화 (버전에 따라 다름)
        for idx, row in enumerate(reader):
            def g(keys, default=0.0):
                for k in keys:
                    if k in row:
                        try: return float(row[k])
                        except: pass
                return default

            area     = g(["Area", "area", "area_px"])
            circ     = g(["Circularity", "circularity"])
            cx       = g(["Centroid_X", "centroid_x", "X"])
            cy       = g(["Centroid_Y", "centroid_y", "Y"])
            mean_int = g(["Mean_Intensity", "mean_intensity", "Intensity"])

            organoids.append(OrganoIDOrganoid(
                id=idx + 1,
                area_px=round(area, 1),
                circularity=round(min(circ, 1.0), 4),
                centroid_x=round(cx, 1),
                centroid_y=round(cy, 1),
                mean_intensity=round(mean_int, 2),
            ))
            areas.append(area)
            circularities.append(min(circ, 1.0))
            intensities.append(mean_int)

    if not organoids:
        raise RuntimeError("OrganoID CSV 파싱 결과 오가노이드 0개")

    n             = len(organoids)
    mean_area     = round(float(np.mean(areas)), 1)
    size_cv       = round(float(np.std(areas) / (np.mean(areas) + 1e-6) * 100), 2)
    mean_circ     = round(float(np.mean(circularities)), 3)
    viability     = round(min(99.0, float(np.mean(intensities)) / 255 * 120), 1)
    qc_score      = round(
        (1 - min(size_cv / 30, 1)) * 40
        + mean_circ * 30
        + (viability / 100) * 30, 1
    )
    osi_pass = (size_cv < 10) and (viability >= 70)

    w, h = img.size
    return OrganoIDResult(
        organoid_count=n,
        mean_area_px=mean_area,
        size_cv=size_cv,
        mean_circularity=mean_circ,
        viability_proxy=viability,
        qc_score=qc_score,
        osi_pass=osi_pass,
        organoids=organoids,
        image_width=w,
        image_height=h,
        image_channels=len(img.getbands()),
        saved_path=saved_path,
        analysis_mode="organoID",
    )


# ══════════════════════════════════════════════
# 공개 인터페이스
# ══════════════════════════════════════════════

def _save_upload(image_bytes: bytes, original_filename: str) -> str:
    """
    업로드 이미지를 uploads/ 에 UUID 이름으로 저장.
    Returns: 저장된 파일 경로 (str)
    """
    ext = Path(original_filename).suffix.lower() or ".png"
    uid = uuid.uuid4().hex[:12]
    dest = UPLOAD_DIR / f"{uid}{ext}"
    dest.write_bytes(image_bytes)
    logger.info(f"이미지 저장: {dest}")
    return str(dest)


def analyze_image(
    image_bytes: bytes,
    original_filename: str = "upload.png",
) -> OrganoIDResult:
    """
    bytes → 분석 결과 반환.

    우선순위:
      1. OrganoID subprocess (ORGANO_ID_DIR 존재 시)
      2. pixel 분석 (OpenCV 연결 성분)
      3. stub (fallback)
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
    except Exception as e:
        raise ValueError(f"이미지 파싱 실패: {e}")

    # 이미지 저장 (Step 2+)
    saved_path = None
    if KEEP_UPLOADS:
        try:
            saved_path = _save_upload(image_bytes, original_filename)
        except Exception as e:
            logger.warning(f"이미지 저장 실패 (분석은 계속): {e}")

    # ── 분석 모드 선택 ──
    if _organoID_dir_ok:
        logger.info("▶ OrganoID subprocess 분석")
        try:
            return _organoID_subprocess_analyze(img, saved_path)
        except Exception as e:
            logger.warning(f"OrganoID 실패 → pixel fallback: {e}")

    # pixel 분석
    logger.info("▶ Pixel (OpenCV) 분석")
    try:
        return _pixel_analyze(img, saved_path)
    except Exception as e:
        logger.warning(f"Pixel 분석 실패 → stub fallback: {e}")

    # stub
    logger.info("▶ Stub 분석")
    return _stub_analyze(img, saved_path)
