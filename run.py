# =============================================
# run.py — 서버 실행 진입점
# 사용법: python run.py
# 클라우드: reload=False, workers는 환경변수로 제어
# =============================================
import os
import uvicorn
from app.config import HOST, PORT

if __name__ == "__main__":
    # 클라우드 환경에서는 reload=False (소스 변경 없음)
    is_dev = os.getenv("DEV", "false").lower() in ("true", "1")
    uvicorn.run(
        "app.main:app",
        host=HOST,
        port=PORT,
        reload=is_dev,
        log_level="info",
    )
