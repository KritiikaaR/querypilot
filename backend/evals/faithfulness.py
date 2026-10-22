"""Answer faithfulness: does the plain-English answer only say what the result rows show?

Scored with deepeval's FaithfulnessMetric (an LLM judge). Only imported when the eval runs
with --faithfulness, so the default eval needs neither deepeval nor the extra API calls.
"""
import os

os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")  # must be set before deepeval is imported

from deepeval.metrics import FaithfulnessMetric  # noqa: E402
from deepeval.metrics.base_metric import Verdict  # noqa: E402
from deepeval.test_case import LLMTestCase  # noqa: E402

JUDGE_MODEL = "gpt-4o-mini"


class FaithfulnessJudge:
    """judge(question, answer, context) -> {"score", "faithful", "issues", "cost_usd"}.

    - penalize_ambiguous_claims: deepeval rates a claim the context neither supports nor
      contradicts as "borderline" and passes it by default. An answer about query results
      should only state what the rows show, so unsupported claims count against it.
    - threshold 1.0: one wrong or made-up claim makes the answer unfaithful.
    - include_reason=False: the verdicts already explain each failing claim, so we skip the
      extra summary call (3 judge calls per answer instead of 4).
    """

    def __init__(self, model: str = JUDGE_MODEL, threshold: float = 1.0):
        self.model, self.threshold = model, threshold

    def __call__(self, question: str, answer: str, context: str) -> dict:
        metric = FaithfulnessMetric(threshold=self.threshold, model=self.model, include_reason=False,
                                    async_mode=False, penalize_ambiguous_claims=True)
        metric.measure(LLMTestCase(input=question, actual_output=answer, retrieval_context=[context]),
                       _show_indicator=False)
        claims, verdicts = metric.claims or [], metric.verdicts or []
        paired = len(claims) == len(verdicts)
        issues = [f"{claims[i]} -> {v.verdict}: {v.reason}" if paired else f"{v.verdict}: {v.reason}"
                  for i, v in enumerate(verdicts) if v.verdict != Verdict.YES]
        return {"score": round(metric.score, 3), "faithful": metric.score >= self.threshold,
                "issues": issues, "cost_usd": metric.evaluation_cost or 0.0}
