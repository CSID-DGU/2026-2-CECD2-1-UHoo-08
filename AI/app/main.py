from fastapi import FastAPI

from api.internal.admin_router import router as admin_router
from api.internal.review_admin_router import router as review_admin_router
from api.internal.agent_router import router as agent_router
from api.internal.recognize_router import router as recognize_router
from api.search_router import router as search_router
from api.internal.v2 import router as v2_router

app = FastAPI(title="BeautyMatch AI Server")

app.include_router(admin_router)
app.include_router(review_admin_router)
app.include_router(agent_router, prefix="/internal")
app.include_router(recognize_router, prefix="/internal")
app.include_router(search_router, prefix="/internal")
# v2 경로. 기존 /internal/agent/run(ReAct)은 그대로 두고 옆에 붙인다.
app.include_router(v2_router, prefix="/internal")
