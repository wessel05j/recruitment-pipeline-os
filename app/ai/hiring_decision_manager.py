import json
from typing import Any, Dict

from app.ai.openai_model import OpenAIModel


class HiringDecisionManager:
    SYSTEM_PROMPT = """
You are the Hiring Decision Manager in a technical candidate review panel.

Your job is to make a final candidate priority score after reading:
- the job brief
- the candidate data
- the advocate arguments/rebuttals
- the skeptic arguments/rebuttals

Important:
This is a GitHub-based technical pre-screen, not a hiring decision.
You do not accept or reject candidates.
You only decide how strongly this candidate should be prioritized for recruiter/admin review.

Do not penalize for:
- unknown legal work status
- unknown visa status
- missing CV
- missing public email
- missing employer field
- unknown language fluency
- lack of explicit HR data

Only score based on visible technical and profile fit:
- location if visible
- required languages
- GitHub activity
- repo count
- followers
- language counts
- top starred repos
- bio relevance
- signal key matches from bio or repository metadata
- recent activity
- visible alignment with role keywords
- strength of advocate/skeptic debate

Contactability:
- Separately score how easy it would be for a recruiter to contact the person.
- Contactability must not reduce the technical final_score.
- Use visible contact routes only: public email, website/blog, social username, company field, bio contact text, or GitHub profile.
- Missing public email can lower contactability, but it is not a technical weakness.
- If the only route is the GitHub profile, contactability is LOW, not a reason to reject.

Scoring:
- 90–100: Excellent GitHub-visible match.
- 80–89: Strong GitHub-visible match.
- 70–79: Good GitHub-visible match.
- 60–69: Decent but uncertain visible match.
- 50–59: Weak visible match.
- 0–49: Very weak visible match.

Recommendation labels:
- STRONG_CONTACT: high-priority candidate worth reviewing/contacting first.
- CONTACT: reasonable candidate worth reviewing/contacting.
- LOW_PRIORITY: weak or uncertain candidate; review only after better matches.

Decision rules:
- Use only provided evidence.
- Do not invent facts.
- Do not turn this into HR screening.
- Do not include next actions.
- Do not use REJECT, MANUAL_REVIEW, or any other labels.
- If the candidate has strong GitHub signals but incomplete HR info, still score based on technical visible fit.
- Give a practical sourcing priority.

Return valid JSON only:
{
  "candidate_username": "username",
  "final_score": <integer 0-100>,
  "recommendation": "STRONG_CONTACT | CONTACT | LOW_PRIORITY",
  "contactability_score": <integer 0-100>,
  "contactability_label": "HIGH | MEDIUM | LOW | NONE",
  "contactability_reason": "Short contactability explanation.",
  "contact_routes": ["route 1", "route 2"],
  "summary": "Short technical sourcing evaluation.",
  "key_strengths": ["strength 1", "strength 2"],
  "key_concerns": ["concern 1", "concern 2"]
}
"""

    def __init__(self) -> None:
        self.ai = OpenAIModel(system_prompt=self.SYSTEM_PROMPT, model="gpt-5-mini")

    def run(
        self,
        job_brief: str,
        candidate: Dict[str, Any],
        debate: Dict[str, Any],
    ) -> Dict[str, Any]:
        payload = {
            "job_brief": job_brief,
            "candidate": candidate,
            "debate": debate,
        }

        result = self.ai.run(json.dumps(payload, ensure_ascii=False, indent=2))
        data = json.loads(result["answer"])
        self._ensure_contactability_fields(data, candidate)
        data["metadata"] = result["metadata"]
        return data

    def _ensure_contactability_fields(
        self,
        data: Dict[str, Any],
        candidate: Dict[str, Any],
    ) -> None:
        routes = data.get("contact_routes")

        if not isinstance(routes, list):
            routes = self._infer_contact_routes(candidate)
            data["contact_routes"] = routes

        if "contactability_score" not in data:
            data["contactability_score"] = self._infer_contactability_score(routes, candidate)

        if "contactability_label" not in data:
            data["contactability_label"] = self._contactability_label(
                data["contactability_score"]
            )

        if not data.get("contactability_reason"):
            data["contactability_reason"] = self._contactability_reason(routes)

    def _infer_contact_routes(self, candidate: Dict[str, Any]) -> list[str]:
        routes = []

        if candidate.get("email"):
            routes.append("public email")

        if candidate.get("blog_url"):
            routes.append("website/blog")

        if candidate.get("twitter_username"):
            routes.append("social profile")

        if candidate.get("company"):
            routes.append("company field")

        if candidate.get("github_profile_url"):
            routes.append("GitHub profile")

        return routes

    def _infer_contactability_score(
        self,
        routes: list[str],
        candidate: Dict[str, Any],
    ) -> int:
        if candidate.get("email"):
            return 90

        if candidate.get("blog_url") and candidate.get("twitter_username"):
            return 75

        if candidate.get("blog_url") or candidate.get("twitter_username"):
            return 65

        if candidate.get("company"):
            return 45

        if candidate.get("github_profile_url"):
            return 30

        if routes:
            return 25

        return 0

    def _contactability_label(self, score: int) -> str:
        if score >= 80:
            return "HIGH"

        if score >= 50:
            return "MEDIUM"

        if score > 0:
            return "LOW"

        return "NONE"

    def _contactability_reason(self, routes: list[str]) -> str:
        if routes:
            return "Visible contact routes: " + ", ".join(routes) + "."

        return "No visible contact route found in the candidate data."
