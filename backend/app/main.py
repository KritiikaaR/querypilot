import logging
import os
from functools import lru_cache

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .agent import TextToSQLAgent
from .config import settings
from .db import Database
from .llm import OpenAIClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("querypilot")

app = FastAPI(title="QueryPilot", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

EXAMPLE_QUESTIONS = [
    "What were the 5 best-selling pizzas by revenue in July?",
    "What hour of the day gets the most orders?",
    "How much revenue did each pizza size bring in?",
    "Which pizzas contain mushrooms?",
    "What was the total revenue each month?",
    "Which day of the week is busiest?",
]


@lru_cache
def get_db() -> Database:
    return Database(settings.db_path)


@lru_cache
def _build_agent() -> TextToSQLAgent:
    return TextToSQLAgent(
        db=get_db(),
        llm=OpenAIClient(settings.openai_model),
        max_attempts=settings.max_attempts,
        max_rows=settings.max_rows,
        timeout_ms=settings.query_timeout_ms,
        summarize=settings.summarize,
    )


def get_agent() -> TextToSQLAgent:
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY is not set on the server.")
    return _build_agent()


class QueryRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)


@app.get("/api/health")
def health():
    return {"status": "ok", "model": settings.openai_model}


@app.get("/api/schema")
def schema(db: Database = Depends(get_db)):
    return {"tables": db.tables()}


@app.get("/api/examples")
def examples():
    return {"examples": EXAMPLE_QUESTIONS}


@app.post("/api/query")
def query(req: QueryRequest, agent: TextToSQLAgent = Depends(get_agent)):
    try:
        result = agent.ask(req.question.strip())
    except Exception as e:  # LLM/network failures: log the detail, return a clean error
        log.exception("query failed")
        raise HTTPException(status_code=502, detail=f"Upstream model error: {type(e).__name__}") from e
    log.info("q=%r status=%s attempts=%d tokens=%d/%d total_ms=%.0f",
             result.question, result.status, len(result.attempts),
             result.input_tokens, result.output_tokens, result.total_ms)
    return result.to_dict()
