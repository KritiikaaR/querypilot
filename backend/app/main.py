import logging
import os
from functools import lru_cache

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .agent import TextToSQLAgent
from .config import settings
from .db import Database
from .llm import OpenAIClient
from .ratelimit import DailyBudget, RateLimiter, client_ip, seconds_until_utc_midnight

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


# Shown to users as-is by the frontend.
TOO_MANY_PER_MINUTE = "You're asking a lot of questions! Try again in a minute."
TOO_MANY_TODAY = "You've asked a lot of questions today. Try again tomorrow."
BUDGET_SPENT = "The demo hit its daily limit. Try again tomorrow."


@lru_cache
def get_rate_limiter() -> RateLimiter:
    return RateLimiter(per_minute=settings.rate_limit_per_minute, per_day=settings.rate_limit_per_day)


@lru_cache
def get_budget() -> DailyBudget:
    return DailyBudget(limit_usd=settings.daily_budget_usd)


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
def query(req: QueryRequest, request: Request,
          agent: TextToSQLAgent = Depends(get_agent),
          limiter: RateLimiter = Depends(get_rate_limiter),
          budget: DailyBudget = Depends(get_budget)):
    if budget.exhausted():
        raise HTTPException(status_code=503, detail=BUDGET_SPENT,
                            headers={"Retry-After": str(seconds_until_utc_midnight(budget.clock()))})
    ip = client_ip(request.headers, request.client.host if request.client else None, settings.trust_proxy)
    hit = limiter.check(ip)
    if hit:
        log.info("rate limited ip=%s limit=%s", ip, hit)
        raise HTTPException(status_code=429, detail=TOO_MANY_PER_MINUTE if hit == "minute" else TOO_MANY_TODAY,
                            headers={"Retry-After": "60" if hit == "minute"
                                     else str(seconds_until_utc_midnight(limiter.clock()))})
    try:
        result = agent.ask(req.question.strip())
    except Exception as e:  # LLM/network failures: log the detail, return a clean error
        log.exception("query failed")
        raise HTTPException(status_code=502, detail=f"Upstream model error: {type(e).__name__}") from e
    budget.charge(result.input_tokens, result.output_tokens)
    log.info("q=%r status=%s attempts=%d tokens=%d/%d total_ms=%.0f",
             result.question, result.status, len(result.attempts),
             result.input_tokens, result.output_tokens, result.total_ms)
    return result.to_dict()
