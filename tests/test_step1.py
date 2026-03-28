# =============================================
# tests/test_step1.py
# 실행: pytest tests/test_step1.py -v
# =============================================
import io
import sys
import os

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from PIL import Image
import numpy as np

from app.main import app

client = TestClient(app)


def make_dummy_image(width=200, height=200, bright=True) -> bytes:
    """테스트용 더미 이미지 생성"""
    arr = np.full((height, width, 3), 200 if bright else 50, dtype=np.uint8)
    # 밝은 원 몇 개 추가
    if bright:
        for cx, cy in [(60,60),(140,60),(60,140),(140,140)]:
            for x in range(width):
                for y in range(height):
                    if (x-cx)**2 + (y-cy)**2 < 30**2:
                        arr[y, x] = [240, 240, 240]
    img = Image.fromarray(arr)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_root():
    r = client.get("/")
    assert r.status_code == 200
    assert "OrganoidQC Bridge" in r.json()["service"]


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    # Step 1에서는 모델 미로드 상태
    assert data["organoID_loaded"] == False


def test_analyze_stub_bright():
    """밝은 이미지 → 높은 viability_proxy 기대"""
    img_bytes = make_dummy_image(bright=True)
    r = client.post("/analyze", files={"file": ("test.png", img_bytes, "image/png")})
    assert r.status_code == 200
    data = r.json()
    assert data["success"] == True
    result = data["result"]
    assert result["analysis_mode"] == "stub"
    assert result["organoid_count"] >= 1
    assert 0 <= result["size_cv"]
    assert 0 <= result["mean_circularity"] <= 1
    print(f"\n[bright] count={result['organoid_count']}, cv={result['size_cv']}, "
          f"viab={result['viability_proxy']}, qc={result['qc_score']}")


def test_analyze_stub_dark():
    """어두운 이미지 → 낮은 viability_proxy 기대"""
    img_bytes = make_dummy_image(bright=False)
    r = client.post("/analyze", files={"file": ("dark.png", img_bytes, "image/png")})
    assert r.status_code == 200
    result = r.json()["result"]
    assert result["viability_proxy"] < 50
    print(f"\n[dark]   count={result['organoid_count']}, cv={result['size_cv']}, "
          f"viab={result['viability_proxy']}, qc={result['qc_score']}")


def test_analyze_wrong_extension():
    r = client.post("/analyze", files={"file": ("bad.pdf", b"notanimage", "application/pdf")})
    assert r.status_code == 415


def test_analyze_corrupt_image():
    r = client.post("/analyze", files={"file": ("bad.png", b"not-image-bytes", "image/png")})
    assert r.status_code == 200
    assert r.json()["success"] == False
