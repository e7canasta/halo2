from fastapi import FastAPI
from halo.api.routes.openai_routes import router as openai_router
from halo.api.routes.custom_routes import router as custom_router
from halo.api.routes.home_routes import router as home_router
from halo.api.routes.command_routes import router as command_router
from halo.api.routes.command_routes_v2 import router as command_router_v2

app = FastAPI(
    title="Halo Inference API",
    description="API for inference backends with tool-based orchestration",
    version="2.0.0",
)

# Include routers
app.include_router(openai_router, prefix="/v1")
app.include_router(custom_router)
app.include_router(command_router, tags=["tools"])  # New tool-based endpoint (takes priority)
app.include_router(command_router_v2, tags=["tools-v2"])  # Policy-driven chain (opt-in via HALO_DOMAIN env var)
app.include_router(home_router, prefix="/legacy", tags=["legacy"])  # Legacy endpoint moved to /legacy prefix

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
