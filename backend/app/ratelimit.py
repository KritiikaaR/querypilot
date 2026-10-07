"""Abuse and cost limits for the public demo: per-IP request limits and a global
daily spend budget. Everything is in memory, which is fine for one instance;
counts reset when the process restarts."""
import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Callable

# gpt-4o-mini list prices, USD per 1M tokens. Used to estimate spend from token counts.
INPUT_USD_PER_M = 0.15
OUTPUT_USD_PER_M = 0.60

Clock = Callable[[], float]  # returns Unix seconds; injectable so tests can move time


def utc_day(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def seconds_until_utc_midnight(ts: float) -> int:
    return max(1, 86_400 - int(ts) % 86_400)


def estimate_cost_usd(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens * INPUT_USD_PER_M + output_tokens * OUTPUT_USD_PER_M) / 1_000_000


class RateLimiter:
    """Per-key limits: at most `per_minute` requests in any 60 seconds and `per_day`
    requests per UTC day. `check()` records the request when it is allowed."""

    def __init__(self, per_minute: int = 10, per_day: int = 60, clock: Clock = time.time):
        self.per_minute, self.per_day, self.clock = per_minute, per_day, clock
        self._recent: dict[str, deque] = {}   # key -> timestamps within the last minute
        self._daily: dict[str, int] = {}      # key -> requests today
        self._day = utc_day(clock())
        self._lock = threading.Lock()

    def check(self, key: str) -> str | None:
        """Return None if allowed (and count it), else "minute" or "day" for the limit that was hit."""
        now = self.clock()
        with self._lock:
            today = utc_day(now)
            if today != self._day:  # new UTC day: forget everything from yesterday
                self._day, self._daily, self._recent = today, {}, {}
            recent = self._recent.setdefault(key, deque())
            while recent and recent[0] <= now - 60:
                recent.popleft()
            if self._daily.get(key, 0) >= self.per_day:
                return "day"
            if len(recent) >= self.per_minute:
                return "minute"
            recent.append(now)
            self._daily[key] = self._daily.get(key, 0) + 1
            return None


class DailyBudget:
    """Estimated model spend for the current UTC day. Once it reaches `limit_usd`,
    `exhausted()` stays true until the next UTC day. Checked before a request and
    charged after it, so the last request of the day can go slightly over."""

    def __init__(self, limit_usd: float = 1.00, clock: Clock = time.time):
        self.limit_usd, self.clock = limit_usd, clock
        self._day = utc_day(clock())
        self.spent_usd = 0.0
        self._lock = threading.Lock()

    def _roll(self) -> None:
        today = utc_day(self.clock())
        if today != self._day:
            self._day, self.spent_usd = today, 0.0

    def exhausted(self) -> bool:
        with self._lock:
            self._roll()
            return self.spent_usd >= self.limit_usd

    def charge(self, input_tokens: int, output_tokens: int) -> None:
        with self._lock:
            self._roll()
            self.spent_usd += estimate_cost_usd(input_tokens, output_tokens)


def client_ip(headers, peer: str | None, trust_proxy: bool) -> str:
    """The caller's IP. Behind a proxy we trust, that's the first X-Forwarded-For
    entry; otherwise it's the socket peer (X-Forwarded-For can be forged)."""
    if trust_proxy:
        forwarded = headers.get("x-forwarded-for", "")
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return peer or "unknown"
