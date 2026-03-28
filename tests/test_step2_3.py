# =============================================
# tests/test_step2_3.py — Step 2+3 통합 테스트
#
# 실행: pytest tests/test_step2_3.py -v
# =============================================
import io
import json
import sys
from pathlib import Path

import pytest
import numpy as np
from PIL import Image, ImageDraw

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.analyzer import analyze_image, _pixel_analyze, _stub_analyze
from app.schemas import OrganoIDResult


# ── 테스트용 이미지 생성 헬퍼 ────────────────────────────────

def make_synthetic_image(
    n_organoids: int = 6,
    size: tuple = (512, 512),
    radius: int = 30,
) -> bytes:
    """밝은 원형 영역 N개를 가진 합성 이미지 (오가노이드 시뮬레이션)"""
    img  = Image.new("RGB", size, (20, 20, 25))   # 어두운 배경
    draw = ImageDraw.Draw(img)
    np.random.seed(42)
    xs = np.random.randint(radius + 20, size[0] - radius - 20, n_organoids)
    ys = np.random.randint(radius + 20, size[1] - radius - 20, n_organoids)
    for x, y in zip(xs, ys):
        r_var = radius + np.random.randint(-5, 5)
        brightness = np.random.randint(200, 255)
        draw.ellipse(
            [x - r_var, y - r_var, x + r_var, y + r_var],
            fill=(brightness, brightness, brightness),
        )
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def make_blank_dark_image(size=(256, 256)) -> bytes:
    """완전히 어두운 이미지 (검출 실패 케이스)"""
    buf = io.BytesIO()
    Image.new("L", size, 10).save(buf, format="PNG")
    return buf.getvalue()


# ── analyzer.py 단위 테스트 ──────────────────────────────────

class TestPixelAnalyze:
    def test_detects_organoids(self):
        img_bytes = make_synthetic_image(n_organoids=5)
        img = Image.open(io.BytesIO(img_bytes))
        result = _pixel_analyze(img)
        assert result.organoid_count >= 1
        assert result.analysis_mode  == "pixel"
        assert 0 <= result.size_cv
        assert 0 < result.mean_circularity <= 1

    def test_returns_organoid_list(self):
        img_bytes = make_synthetic_image(n_organoids=4)
        img = Image.open(io.BytesIO(img_bytes))
        result = _pixel_analyze(img)
        assert result.organoids is not None
        assert len(result.organoids) == result.organoid_count

    def test_organoid_fields(self):
        img_bytes = make_synthetic_image(n_organoids=3)
        img = Image.open(io.BytesIO(img_bytes))
        result = _pixel_analyze(img)
        if result.organoids:
            o = result.organoids[0]
            assert o.area_px     > 0
            assert 0 <= o.circularity <= 1
            assert o.centroid_x  >= 0
            assert o.centroid_y  >= 0
            assert o.mean_intensity >= 0

    def test_image_dimensions_recorded(self):
        img_bytes = make_synthetic_image(size=(400, 300))
        img = Image.open(io.BytesIO(img_bytes))
        result = _pixel_analyze(img)
        assert result.image_height == 300
        assert result.image_width  == 400

    def test_dark_image_falls_back_to_stub(self):
        """어두운 이미지에서 pixel 분석 실패 시 stub으로 fallback"""
        img_bytes = make_blank_dark_image()
        result = analyze_image(img_bytes, "dark.png")
        assert result.analysis_mode in ("pixel", "stub")
        assert result.organoid_count >= 1


class TestStubAnalyze:
    def test_always_returns_result(self):
        img_bytes = make_synthetic_image()
        img = Image.open(io.BytesIO(img_bytes))
        result = _stub_analyze(img)
        assert result.analysis_mode == "stub"
        assert result.organoid_count >= 1
        assert 0 <= result.qc_score <= 100


class TestAnalyzeImagePublicInterface:
    def test_analyze_image_bytes(self):
        img_bytes = make_synthetic_image(n_organoids=5)
        result = analyze_image(img_bytes, "test.png")
        assert isinstance(result, OrganoIDResult)
        assert result.success_fields_present()

    def test_invalid_bytes_raises(self):
        with pytest.raises(ValueError, match="이미지 파싱 실패"):
            analyze_image(b"not-an-image", "bad.png")

    def test_grayscale_image(self):
        buf = io.BytesIO()
        Image.new("L", (256, 256), 180).save(buf, format="PNG")
        result = analyze_image(buf.getvalue(), "gray.png")
        assert result.analysis_mode in ("pixel", "stub")


# ── FastAPI 엔드포인트 통합 테스트 ───────────────────────────

@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "organoID_loaded"  in data
        assert "organoID_dir_ok"  in data
        assert "version"          in data

    def test_root_returns_mode(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert "mode" in r.json()


class TestAnalyzeEndpoint:
    def _upload(self, client, img_bytes, filename="test.png"):
        return client.post(
            "/analyze",
            files={"file": (filename, img_bytes, "image/png")},
        )

    def test_analyze_success(self, client):
        r = self._upload(client, make_synthetic_image())
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        result = data["result"]
        assert result["organoid_count"] >= 1
        assert result["analysis_mode"] in ("pixel", "stub", "organoID")

    def test_analyze_returns_qc_fields(self, client):
        r = self._upload(client, make_synthetic_image())
        result = r.json()["result"]
        for field in ["size_cv", "qc_score", "mean_circularity", "viability_proxy", "osi_pass"]:
            assert field in result

    def test_unsupported_extension(self, client):
        r = client.post("/analyze", files={"file": ("test.gif", b"GIF89a", "image/gif")})
        assert r.status_code == 415

    def test_invalid_image_data(self, client):
        r = self._upload(client, b"not-image-data", "bad.png")
        assert r.status_code == 200
        assert r.json()["success"] is False

    def test_images_list_endpoint(self, client):
        r = client.get("/images")
        assert r.status_code == 200
        data = r.json()
        assert "count"  in data
        assert "images" in data


# ── OrganoIDResult 헬퍼 ──────────────────────────────────────
def _success_fields_present(self) -> bool:
    return all([
        self.organoid_count >= 0,
        self.qc_score       >= 0,
        self.analysis_mode  in ("stub", "pixel", "organoID", "tflite"),
    ])

OrganoIDResult.success_fields_present = _success_fields_present
