from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routers import accounts, sync, config

app = FastAPI(
    title="邮箱同步助手 API",
    description="飞书多维表格邮箱同步插件后端服务",
    version="1.0.0"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(accounts.router)
app.include_router(sync.router)
app.include_router(config.router)


@app.on_event("startup")
async def startup_event():
    init_db()


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "1.0.0"}
