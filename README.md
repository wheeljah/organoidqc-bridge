# OrganoidQC Bridge  
<image-card alt="DOI" src="https://zenodo.org/badge/DOI/10.5281/zenodo.19311801.svg" ></image-card>(https://doi.org/10.5281/zenodo.19311801)
**v0.4.0 — 클라우드 배포 + 연구자 배포 간소화**

OrganoidQC 웹 앱(`OrganoidQC_v5_2.html`)과 OrganoID 분석 엔진을 연결하는 FastAPI 서버.

---

## 구현 현황

| 단계 | 내용 | 상태 |
|------|------|------|
| Step 1 | FastAPI 뼈대 + `/health` + Stub 분석 | ✅ 완료 |
| Step 2 | OpenCV 픽셀 분석 + 이미지 저장 엔드포인트 | ✅ 완료 |
| Step 3 | OrganoID subprocess 파이프라인 연결 | ✅ 완료 |
| Step 4 | OrganoidQC v5.2 HTML fetch 연동 | ✅ 완료 |
| Step 5 | 클라우드 배포 (Railway / Render) | ✅ 완료 |
| Step 6 | 연구자 배포 간소화 (URL 자동감지 + 서버 서빙) | ✅ 완료 |

---

## 연구자에게 전달하는 두 가지 방법

### 방법 A — URL 하나로 완결 (권장) ✅
배포 후 연구자에게 URL 하나만 전달:
```
https://your-app.up.railway.app
```
→ 연구자가 URL을 열면 분석 페이지가 바로 표시됩니다.  
→ 서버와 같은 오리진이므로 Bridge URL 자동 연결, 입력 불필요.

### 방법 B — HTML 파일 배포
`OrganoidQC_v5_2.html` 파일만 연구자에게 전달:
- `file://`로 열면 Bridge URL 입력창이 표시됨
- Railway URL 또는 `http://localhost:8000` 입력 후 사용
- `localStorage`에 저장되어 다음 번엔 입력 불필요

> **Railway URL이 확정되면** HTML 파일 내 `PLACEHOLDER_URL` 한 줄을 실제 URL로 교체하면  
> 파일로 열어도 URL 입력 없이 자동 연결됩니다.

> ⚠️ **v5.2 보안 변경:** Bridge URL은 `https://` 또는 `localhost`만 허용됩니다.  
> 내부망 IP(`10.x`, `192.168.x`, `172.16–31.x`) 입력 시 클라이언트에서 차단됩니다.

---

## 파일 구조

```
organoidqc-bridge/
├── app/
│   ├── main.py            # GET / → HTML 서빙, POST /analyze 등
│   ├── analyzer.py        # OrganoID → pixel → stub
│   ├── schemas.py         # Pydantic 모델
│   └── config.py          # 환경 설정
├── tests/
├── OrganoidQC_v5_2.html   # 서버·파일 양쪽에서 동작 (URL 자동감지)
├── Dockerfile             # HTML + OrganoID + tensorflow 포함
├── railway.json
├── render.yaml
├── .env.example
├── setup_organoID.sh
├── run.py
└── requirements.txt
```

---

## 🚀 클라우드 배포 (Railway)

### 1) GitHub push
```bash
git init && git add . && git commit -m "init"
git remote add origin https://github.com/<you>/organoidqc-bridge.git
git push -u origin main
```

### 2) Railway 배포
1. [railway.app](https://railway.app) → **New Project → Deploy from GitHub**
2. 레포 선택 → `Dockerfile` 자동 감지 → 빌드 시작 (5~10분)
3. **Settings → Networking → Generate Domain**
4. 발급된 URL을 연구자에게 공유

### 3) (선택) HTML 파일 URL 고정
Railway URL 확정 후 `OrganoidQC_v5_2.html`에서 한 줄만 수정:
```javascript
// 변경 전
const PLACEHOLDER_URL = 'https://your-app.up.railway.app';
// 변경 후
const PLACEHOLDER_URL = 'https://organoidqc-xxxx.up.railway.app';
```
이후 `git push` 하면 서버와 파일 배포 모두 자동 반영.

---

## 로컬 실행

```bash
pip install -r requirements.txt
python run.py
# 브라우저에서 http://localhost:8000 열기 (HTML 자동 서빙)
```

---

## API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| GET | `/` | OrganoidQC 웹 앱 HTML (연구자용) |
| GET | `/health` | 서버 상태 + 분석 모드 확인 |
| GET | `/info` | 서버 정보 JSON |
| POST | `/analyze` | 이미지 → QC 지표 JSON |
| GET | `/images` | 저장 이미지 목록 |

분석 모드 우선순위: **OrganoID subprocess → pixel → stub**

### `/analyze` 응답 스펙

v5.2 HTML의 `applyBridgeResult()`가 소비하는 필드입니다. Bridge 서버 응답은 아래 형식을 따라야 합니다.

```json
{
  "success": true,
  "result": {
    "analysis_mode": "organoID",
    "organoid_count": 12,
    "size_cv": 6.8,
    "mean_circularity": 0.83,
    "viability_proxy": 88,
    "qc_score": 91
  }
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `analysis_mode` | string | `"organoID"` \| `"pixel"` \| `"stub"` |
| `organoid_count` | int | 검출된 오가노이드 수 |
| `size_cv` | float | 크기 변동계수 (%) |
| `mean_circularity` | float | 평균 원형도 (0–1) |
| `viability_proxy` | float | 생존율 추정 (%) |
| `qc_score` | int | 종합 QC 점수 (0–100) |

> **v5.2 클라이언트 변경:** 이미지 업로드 시 10MB 초과 파일은 클라이언트에서 차단되어 서버로 전송되지 않습니다.

---

## 환경변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `HOST` | `0.0.0.0` | 서버 바인드 주소 |
| `PORT` | `8000` | 포트 (Railway/Render 자동 주입) |
| `ORGANO_ID_DIR` | `./organoID` | OrganoID 레포 경로 |
| `UPLOAD_DIR` | `./uploads` | 이미지 저장 경로 |
| `KEEP_UPLOADS` | `false` | 이미지 영구 저장 여부 |
| `ALLOWED_ORIGINS` | `*` | CORS 허용 도메인 |
| `DEV` | `false` | `true` 시 uvicorn reload 활성 |

---

## 테스트

```bash
pytest tests/test_step2_3.py -v
```

---

## 변경 이력

| 버전 | 변경 사항 |
|------|-----------|
| v0.4.0 | 클라우드 배포(Railway/Render), HTML 서버 서빙, URL 자동감지 |
| v0.3.0 | OrganoidQC v5.2 HTML 연동, `/analyze` 응답 스펙 확정 |
| v0.2.0 | OrganoID subprocess 파이프라인, pixel 폴백 |
| v0.1.0 | FastAPI 뼈대, `/health`, Stub 분석 |
