import uvicorn
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes.support import router as support_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("support_app")

app = FastAPI(
    title="Customer Support Action Agent API",
    description="LangGraph Human-in-the-Loop (HITL) agent with Tools-Before-Approval and JEV Guardian Evaluator.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register support routes
app.include_router(support_router, prefix="/api")

@app.get("/", tags=["Health"])
async def root():
    return {
        "status": "ok",
        "service": "Customer Support Action Agent (LangGraph + HITL + JEV Guardian)",
        "endpoints": [
            "POST /api/support - Start support request",
            "GET /api/support/{threadId} - Get thread state",
            "POST /api/support/{threadId}/approval - Submit human approval"
        ]
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
