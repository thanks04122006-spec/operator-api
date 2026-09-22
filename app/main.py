from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.errors import register_error_handlers
from app.routers import admin, congestion, meta, stats

app = FastAPI(
    title="용산꿈나무도서관 AI 혼잡도 안내 API",
    description="도서관 방문자 데이터를 기반으로 시간대별 혼잡도를 안내하는 백엔드 API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 배포 시 프론트 도메인으로 제한 권장
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)

app.include_router(congestion.router)
app.include_router(stats.router)
app.include_router(meta.router)
app.include_router(admin.router)


@app.get("/api/v1/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return {"service": "library-congestion-api", "status": "ok"}
