# =============================================
# run.py — 서버 실행 진입점
# 사용법: python run.py
#
# NOTE: Railway가 HOST 환경변수를 내부 hostname으로 자동 주입하므로
#       BIND_HOST를 별도로 사용합니다 (기본값: 0.0.0.0).
# =============================================
import os
import uvicorn

if __name__ == "__main__":
    # Railway의 HOST 변수 충돌 방지 — BIND_HOST 우선 사용
    host = os.getenv("BIND_HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    is_dev = os.getenv("DEV", "false").lower() in ("true", "1")

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=is_dev,
        log_level="info",
    )
