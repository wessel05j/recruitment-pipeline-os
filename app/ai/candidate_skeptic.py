import json
from typing import Any, Dict, List

from app.ai.openai_model import OpenAIModel


class CandidateSkeptic:
    SYSTEM_PROMPT = """
You are the Candidate Skeptic in a recruitment review panel.

Your job is to argue why the candidate may not be a good match for the job brief.

Rules:
- Use only the provided job brief and candidate data.
- Do not invent negative facts.
- Be fair and evidence-based.
- Separate confirmed weaknesses from unknowns.
- Focus on missing hard requirements, weak evidence, missing technologies, unclear seniority, weak activity, location uncertainty, language uncertainty, and lack of production evidence.
- Missing evidence is a risk, not automatic rejection.
- Be concise.

Skeptic scoring perspective:
- Give a conservative risk-adjusted score.
- Penalize missing hard requirements and weak evidence.
- 85–100: Very strong candidate with minimal risk.
- 70–84: Good candidate, but some concerns remain.
- 55–69: Possible fit, but uncertain.
- 40–54: Significant gaps or weak evidence.
- 0–39: Not suitable based on available evidence.

Return valid JSON only:
{
  "role": "candidate_skeptic",
  "round": 1,
  "argument": "Argument against the candidate.",
  "concerns": ["concern 1", "concern 2"],
  "missing_evidence": ["missing evidence 1", "missing evidence 2"],
  "suggested_score": 55
}
"""

    def __init__(self) -> None:
        self.ai = OpenAIModel(system_prompt=self.SYSTEM_PROMPT, model="gpt-5-mini")

    def run(
        self,
        round_number: int,
        job_brief: str,
        candidate: Dict[str, Any],
        previous_arguments: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        payload = {
            "round": round_number,
            "job_brief": job_brief,
            "candidate": candidate,
            "previous_arguments": previous_arguments,
        }
        result = self.ai.run(json.dumps(payload, ensure_ascii=False, indent=2))
        data = json.loads(result["answer"])
        data["metadata"] = result["metadata"]
        return data