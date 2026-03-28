# OrganoidQC Bridge  
**v0.4.0 — 클라우드 배포 + 연구자 배포 간소화**

OrganoidQC 웹 앱과 OrganoID 분석 엔진을 연결하는 FastAPI 서버.

---

## 구현 현황

| 단계 | 내용 | 상태 |
|------|------|------|
| Step 1 | FastAPI 뼈대 + `/health` + Stub 분석 | ✅ 완료 |
| Step 2 | OpenCV 픽셀 분석 + 이미지 저장 엔드포인트 | ✅ 완료 |
| Step 3 | OrganoID subprocess 파이프라인 연결 | ✅ 완료 |
| Step 4 | OrganoidQC v3.8 HTML fetch 연동 | ✅ 완료 |
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
`OrganoidQC_v3_8.html` 파일만 연구자에게 전달:
- `file://`로 열면 Bridge URL 입력창이 표시됨
- Railway URL 또는 `http://localhost:8000` 입력 후 사용
- `localStorage`에 저장되어 다음 번엔 입력 불필요

> **Railway URL이 확정되면** HTML 파일 내 `PLACEHOLDER_URL` 한 줄을 실제 URL로 교체하면  
> 파일로 열어도 URL 입력 없이 자동 연결됩니다.

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
├── OrganoidQC_v3_8.html   # 서버·파일 양쪽에서 동작 (URL 자동감지)
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
Railway URL 확정 후 `OrganoidQC_v3_8.html`에서 한 줄만 수정:
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
