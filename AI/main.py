import asyncio
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from api.internal.recognize_router import router as recognize_router
from api.internal.agent_router import router as agent_router
from api.search_router import router as search_router
from api.iot.router import router as iot_router
from api.care.router import router as care_router
from api.internal.v2 import router as v2_router
from services.influencer_collector import run_schedule

# LangSmith 트레이싱 활성화 (LANGSMITH_API_KEY가 있을 때만)
if settings.LANGSMITH_API_KEY:
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = settings.LANGSMITH_API_KEY
    os.environ["LANGCHAIN_PROJECT"] = settings.LANGSMITH_PROJECT

app = FastAPI(title="Cosmetic AI Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # 운영 환경에서는 Spring Backend 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(recognize_router, prefix="/internal")
app.include_router(agent_router, prefix="/internal")
app.include_router(search_router, prefix="/internal")
app.include_router(iot_router)     # ESP32 직접 호출, /internal 밖
app.include_router(care_router)    # 키오스크 직접 호출, /internal 밖
# v2 경로. 기존 /internal/agent/run(ReAct)은 그대로 두고 옆에 붙인다.
app.include_router(v2_router, prefix="/internal")

@app.on_event("startup")
async def startup_event():
    # bge-m3 사전 로드 — embedding_service 완성 후 아래 주석 해제
    # from services.embedding_service import warmup
    # await warmup()

    # 인플루언서 게시물 수집. 오늘 안 모으면 오늘 것은 영영 없어서 앱과 같이 뜬다.
    app.state.influencer_schedule = asyncio.create_task(run_schedule())
