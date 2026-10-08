"""Per-IP rate limits, the daily budget, client IP detection, and the OpenAI client
settings. All API calls use FakeLLM; time is driven by a fake clock."""
from dataclasses import replace
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.agent import TextToSQLAgent
from app.main import BUDGET_SPENT, TOO_MANY_PER_MINUTE, TOO_MANY_TODAY, app, get_agent, get_budget, get_db, get_rate_limiter
from app.ratelimit import DailyBudget, RateLimiter, client_ip, estimate_cost_usd, seconds_until_utc_midnight

NOON = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc).timestamp()
OK_REPLY = {"sql": "SELECT COUNT(*) AS n FROM pizzas", "explanation": "Counts menu items."}


class Clock:
    def __init__(self, t: float = NOON):
        self.t = t

    def __call__(self) -> float:
        return self.t


# ---------- RateLimiter ----------

def test_per_minute_limit_then_window_slides():
    clock = Clock()
    rl = RateLimiter(per_minute=10, per_day=60, clock=clock)
    assert all(rl.check("1.1.1.1") is None for _ in range(10))
    assert rl.check("1.1.1.1") == "minute"
    assert rl.check("2.2.2.2") is None          # other IPs are unaffected
    clock.t += 61
    assert rl.check("1.1.1.1") is None          # oldest requests left the 60 s window


def test_blocked_requests_dont_count():
    clock = Clock()
    rl = RateLimiter(per_minute=2, per_day=3, clock=clock)
    rl.check("ip"), rl.check("ip")
    assert rl.check("ip") == "minute"
    clock.t += 61
    assert rl.check("ip") is None               # 3rd allowed request today
    assert rl.check("ip") == "day"


def test_per_day_limit_resets_next_utc_day():
    clock = Clock()
    rl = RateLimiter(per_minute=10, per_day=60, clock=clock)
    for _ in range(6):
        for _ in range(10):
            assert rl.check("ip") is None
        clock.t += 61
    assert rl.check("ip") == "day"              # 60 used, even though the minute window is empty
    clock.t = datetime(2026, 3, 11, 0, 0, 1, tzinfo=timezone.utc).timestamp()
    assert rl.check("ip") is None


# ---------- DailyBudget ----------

def test_cost_uses_gpt_4o_mini_prices():
    assert estimate_cost_usd(1_000_000, 0) == pytest.approx(0.15)
    assert estimate_cost_usd(0, 1_000_000) == pytest.approx(0.60)


def test_budget_exhausts_and_resets_at_utc_midnight():
    clock = Clock()
    b = DailyBudget(limit_usd=1.00, clock=clock)
    b.charge(4_000_000, 0)                      # $0.60
    assert not b.exhausted()
    b.charge(0, 700_000)                        # +$0.42 -> $1.02
    assert b.exhausted()
    clock.t = datetime(2026, 3, 10, 23, 59, 59, tzinfo=timezone.utc).timestamp()
    assert b.exhausted()                        # still the same UTC day
    clock.t += 2
    assert not b.exhausted() and b.spent_usd == 0


def test_seconds_until_utc_midnight():
    assert seconds_until_utc_midnight(NOON) == 12 * 3600
    assert seconds_until_utc_midnight(datetime(2026, 3, 11, tzinfo=timezone.utc).timestamp()) == 86_400


# ---------- client IP ----------

def test_client_ip_uses_first_forwarded_entry_only_when_trusted():
    headers = {"x-forwarded-for": "203.0.113.7, 10.0.0.2"}
    assert client_ip(headers, "10.0.0.1", trust_proxy=True) == "203.0.113.7"
    assert client_ip(headers, "10.0.0.1", trust_proxy=False) == "10.0.0.1"
    assert client_ip({}, "10.0.0.1", trust_proxy=True) == "10.0.0.1"
    assert client_ip({}, None, trust_proxy=False) == "unknown"


# ---------- API ----------

@pytest.fixture
def api(db, fake_llm):
    """A TestClient plus the limiter, budget, and FakeLLM behind it."""
    clock = Clock()
    state = {"limiter": RateLimiter(per_minute=10, per_day=60, clock=clock),
             "budget": DailyBudget(limit_usd=1.00, clock=clock), "clock": clock}

    def use(replies):
        state["llm"] = fake_llm(replies)
        agent = TextToSQLAgent(db, state["llm"], max_rows=50, timeout_ms=1000)
        app.dependency_overrides[get_agent] = lambda: agent

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_rate_limiter] = lambda: state["limiter"]
    app.dependency_overrides[get_budget] = lambda: state["budget"]
    state["use"], state["client"] = use, TestClient(app)
    yield state
    app.dependency_overrides.clear()


def ask(client, **headers):
    return client.post("/api/query", json={"question": "How many menu items?"}, headers=headers)


def test_eleventh_request_in_a_minute_gets_friendly_429(api):
    api["use"]([OK_REPLY] * 10)
    assert all(ask(api["client"]).status_code == 200 for _ in range(10))
    r = ask(api["client"])
    assert r.status_code == 429
    assert r.json() == {"detail": TOO_MANY_PER_MINUTE}
    assert TOO_MANY_PER_MINUTE == "You're asking a lot of questions! Try again in a minute."
    assert r.headers["retry-after"] == "60"
    assert api["llm"].replies == []             # the blocked request never reached the model


def test_daily_ip_limit_gets_its_own_message(api):
    api["limiter"] = RateLimiter(per_minute=10, per_day=2, clock=api["clock"])
    api["use"]([OK_REPLY] * 2)
    ask(api["client"]), ask(api["client"])
    r = ask(api["client"])
    assert r.status_code == 429 and r.json()["detail"] == TOO_MANY_TODAY
    assert r.headers["retry-after"] == str(12 * 3600)


def test_budget_is_charged_from_token_usage_then_returns_503(api):
    one_call = estimate_cost_usd(100, 20)       # FakeLLM reports 100 in / 20 out per call
    api["budget"].limit_usd = one_call          # the first answer uses up the whole budget
    api["use"]([OK_REPLY])                      # one scripted reply: a second model call would 502
    assert ask(api["client"]).status_code == 200
    assert api["budget"].spent_usd == pytest.approx(one_call)
    r = ask(api["client"])
    assert r.status_code == 503
    assert r.json() == {"detail": BUDGET_SPENT}
    assert BUDGET_SPENT == "The demo hit its daily limit. Try again tomorrow."
    assert r.headers["retry-after"] == str(12 * 3600)


def test_budget_503_lasts_until_next_utc_day(api):
    api["budget"].limit_usd = 0.0
    api["use"]([OK_REPLY])
    assert ask(api["client"]).status_code == 503
    api["clock"].t = datetime(2026, 3, 11, 0, 0, 1, tzinfo=timezone.utc).timestamp()
    api["budget"].limit_usd = 1.0
    assert ask(api["client"]).status_code == 200


def test_trust_proxy_limits_each_forwarded_ip(api, monkeypatch):
    api["limiter"] = RateLimiter(per_minute=1, per_day=60, clock=api["clock"])
    api["use"]([OK_REPLY] * 3)
    monkeypatch.setattr(main, "settings", replace(main.settings, trust_proxy=True))
    assert ask(api["client"], **{"X-Forwarded-For": "198.51.100.1"}).status_code == 200
    assert ask(api["client"], **{"X-Forwarded-For": "198.51.100.2, 10.0.0.9"}).status_code == 200
    assert ask(api["client"], **{"X-Forwarded-For": "198.51.100.1"}).status_code == 429


def test_forwarded_header_ignored_without_trust_proxy(api, monkeypatch):
    api["limiter"] = RateLimiter(per_minute=1, per_day=60, clock=api["clock"])
    api["use"]([OK_REPLY])
    monkeypatch.setattr(main, "settings", replace(main.settings, trust_proxy=False))
    assert ask(api["client"], **{"X-Forwarded-For": "198.51.100.1"}).status_code == 200
    # A forged header can't buy a fresh quota: both requests count against the socket IP.
    assert ask(api["client"], **{"X-Forwarded-For": "198.51.100.2"}).status_code == 429


# ---------- OpenAI client ----------

def test_openai_client_timeout_and_retries(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")  # constructing the client makes no network call
    from app.llm import OpenAIClient
    c = OpenAIClient("gpt-4o-mini")
    assert c.client.timeout == 20
    assert c.client.max_retries == 1
