import json
from pathlib import Path
from typing import Any, Dict, List

from app.ai.openai_model import OpenAIModel


class CandidateFormatBuilder:
    """
    Converts ranked, admin-approved candidates into report-ready sections.

    This step formats evidence. It does not approve, reject, rerank, or rescore.
    """

    JOB_BRIEF_PATH = Path("app/temp/job_brief.txt")
    ADMIN_PASS_PATH = Path("app/temp/admin_candidates_pass.json")
    OUTPUT_DIR = Path("app/temp")
    OUTPUT_FILE = "candidate_report_sections.json"

    SYSTEM_PROMPT = """
You are the Candidate Format Builder for a recruitment sourcing report.

Your job:
- Convert ranked, admin-approved GitHub candidate metadata into polished report sections.
- Preserve the existing rank, final score, recommendation, contactability, strengths, concerns, and evidence.
- Handle missing fields gracefully.

Important:
- Do not approve, reject, rerank, or rescore candidates.
- Do not invent facts.
- Do not add employment history, education, years of experience, or technologies unless they are visible in the provided metadata.
- Missing public email should be written as "No public email found".
- Missing company should be written as "Not listed".
- Missing website/social routes should be written naturally as missing contact routes.
- Use GitHub evidence: languages, signal matches, latest activity, followers, repo count, and top repositories.
- Prefer top_relevant_repos over top_starred_repos when choosing notable repositories.
- Treat source_fit_score as source-stage evidence, not the final candidate score.
- Keep text client-ready, concise, and factual.
- technical_fit_summary must be 40-70 words.
- why_selected must contain at most 2 bullets.
- possible_concerns must contain at most 2 bullets.
- suggested_questions must contain at most 2 bullets.
- notable_repositories must contain at most 3 repositories.

Return valid JSON only:
{
  "report_title": "GitHub Candidate Shortlist",
  "role_summary": "Short plain-language role summary.",
  "candidate_count": <integer>,
  "candidates": [
    {
      "rank": <integer>,
      "display_name": "Name or username",
      "headline": "Short one-line candidate headline.",
      "github_profile_url": "https://github.com/username",
      "score": <integer>,
      "recommendation": "STRONG_CONTACT | CONTACT | LOW_PRIORITY",
      "contactability": {
        "label": "HIGH | MEDIUM | LOW | NONE",
        "score": <integer>,
        "routes": ["route 1", "route 2"],
        "note": "Short contactability note."
      },
      "profile": {
        "location": "Location or Not listed",
        "company": "Company or Not listed",
        "public_email": "Email or No public email found",
        "website": "Website or Not listed",
        "social": "Social handle or Not listed",
        "followers": <integer or null>,
        "repo_count": <integer or null>,
        "latest_activity": "Timestamp or Not listed"
      },
      "technical_fit_summary": "Short evidence-based fit summary.",
      "why_selected": ["reason 1", "reason 2"],
      "possible_concerns": ["concern 1", "concern 2"],
      "suggested_questions": ["evidence-based interview or screening question"],
      "github_evidence": {
        "matched_languages": ["language 1"],
        "signal_matches": ["key matched in field"],
        "notable_repositories": [
          {
            "name": "repo name",
            "description": "description or Not listed",
            "stars": <integer or null>,
            "language": "language or Not listed",
            "url": "repo url"
          }
        ]
      }
    }
  ]
}
"""

    def __init__(self) -> None:
        self.ai = OpenAIModel(
            system_prompt=self.SYSTEM_PROMPT,
            model="gpt-5-mini",
            use_memory=False,
        )

    def run(self) -> Path:
        job_brief = self._load_job_brief()
        admin_pass = self._load_admin_pass()

        if not admin_pass.get("candidates"):
            output = {
                "report_title": "GitHub Candidate Shortlist",
                "role_summary": "No candidates passed admin review.",
                "candidate_count": 0,
                "candidates": [],
            }
            return self._save_output(output)

        payload = {
            "job_brief": job_brief,
            "approved_candidates": admin_pass,
        }

        result = self.ai.run(json.dumps(payload, ensure_ascii=False, indent=2))
        parsed = self._parse_json(result["answer"])
        self._normalize_report(parsed, admin_pass)
        parsed["metadata"] = result["metadata"]

        return self._save_output(parsed)

    def _load_job_brief(self) -> str:
        if not self.JOB_BRIEF_PATH.exists():
            raise FileNotFoundError(f"Missing job brief: {self.JOB_BRIEF_PATH}")

        return self.JOB_BRIEF_PATH.read_text(encoding="utf-8")

    def _load_admin_pass(self) -> Dict[str, Any]:
        if not self.ADMIN_PASS_PATH.exists():
            raise FileNotFoundError(f"Missing admin pass file: {self.ADMIN_PASS_PATH}")

        return json.loads(self.ADMIN_PASS_PATH.read_text(encoding="utf-8"))

    def _save_output(self, output: Dict[str, Any]) -> Path:
        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = self.OUTPUT_DIR / self.OUTPUT_FILE

        with output_path.open("w", encoding="utf-8") as file:
            json.dump(output, file, ensure_ascii=False, indent=2)

        print(f"Candidate report sections saved to: {output_path}")
        return output_path

    def _parse_json(self, raw_answer: str) -> Dict[str, Any]:
        try:
            data = json.loads(raw_answer)
        except json.JSONDecodeError:
            cleaned = raw_answer.strip()

            if cleaned.startswith("```json"):
                cleaned = cleaned.removeprefix("```json").removesuffix("```").strip()
            elif cleaned.startswith("```"):
                cleaned = cleaned.removeprefix("```").removesuffix("```").strip()

            try:
                data = json.loads(cleaned)
            except json.JSONDecodeError:
                raise ValueError(f"AI did not return valid JSON:\n{raw_answer}")

        if not isinstance(data.get("candidates"), list):
            raise ValueError("Candidate format output must include a candidates list.")

        if data.get("candidate_count") != len(data["candidates"]):
            data["candidate_count"] = len(data["candidates"])

        if not data.get("report_title"):
            data["report_title"] = "GitHub Candidate Shortlist"

        if not data.get("role_summary"):
            data["role_summary"] = "Role summary not available."

        return data

    def _normalize_report(
        self,
        report: Dict[str, Any],
        admin_pass: Dict[str, Any],
    ) -> None:
        source_candidates = {
            item.get("rank"): item for item in admin_pass.get("candidates", [])
        }

        for candidate in report.get("candidates", []):
            source = source_candidates.get(candidate.get("rank"), {})
            self._normalize_candidate(candidate, source)

        report["candidate_count"] = len(report.get("candidates", []))

    def _normalize_candidate(
        self,
        candidate: Dict[str, Any],
        source: Dict[str, Any],
    ) -> None:
        source_candidate = source.get("candidate", {})
        source_assessment = source.get("assessment", {})

        candidate["rank"] = source.get("rank", candidate.get("rank"))
        candidate["display_name"] = candidate.get("display_name") or (
            source_candidate.get("name")
            or source_candidate.get("username")
            or "Unknown candidate"
        )
        candidate["github_profile_url"] = (
            source_candidate.get("github_profile_url")
            or candidate.get("github_profile_url")
            or ""
        )
        candidate["score"] = source_assessment.get("final_score", candidate.get("score"))
        candidate["recommendation"] = source_assessment.get(
            "recommendation",
            candidate.get("recommendation"),
        )

        candidate["technical_fit_summary"] = self._shorten(
            candidate.get("technical_fit_summary")
            or source_assessment.get("summary")
            or "No technical fit summary available.",
            max_words=70,
        )
        candidate["why_selected"] = self._limit_list(
            candidate.get("why_selected") or source_assessment.get("key_strengths", []),
            limit=2,
        )
        candidate["possible_concerns"] = self._limit_list(
            candidate.get("possible_concerns") or source_assessment.get("key_concerns", []),
            limit=2,
        )
        candidate["suggested_questions"] = self._limit_list(
            candidate.get("suggested_questions", []),
            limit=2,
        )
        if not candidate["suggested_questions"]:
            candidate["suggested_questions"] = [
                "Which public repository best represents the work most relevant to this role?",
                "What parts of this work were used in a real workflow or production-like setting?",
            ]

        candidate["contactability"] = self._contactability(source_assessment)
        candidate["profile"] = self._profile(source_candidate)
        candidate["github_evidence"] = self._github_evidence(source_candidate)

    def _contactability(self, assessment: Dict[str, Any]) -> Dict[str, Any]:
        routes = assessment.get("contact_routes", [])
        clues = assessment.get("contact_research_clues", [])
        note = assessment.get("contactability_reason") or "No contactability note."

        if clues and not routes:
            note = note + " Research required before outreach."

        return {
            "label": assessment.get("contactability_label", "NONE"),
            "score": assessment.get("contactability_score", 0),
            "routes": routes,
            "research_clues": clues,
            "note": note,
        }

    def _profile(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "location": candidate.get("location") or "Not listed",
            "company": candidate.get("company") or "Not listed",
            "public_email": candidate.get("email") or "No public email found",
            "website": candidate.get("blog_url") or "Not listed",
            "social": candidate.get("twitter_username") or "Not listed",
            "followers": candidate.get("followers"),
            "repo_count": candidate.get("repo_count"),
            "latest_activity": candidate.get("latest_repo_push") or "Not listed",
        }

    def _github_evidence(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "matched_languages": candidate.get("matched_languages", []),
            "source_fit_score": candidate.get("source_fit_score"),
            "source_fit_reasons": candidate.get("source_fit_reasons", []),
            "signal_matches": self._signal_match_lines(
                candidate.get("signal_matches", [])
            ),
            "notable_repositories": self._notable_repositories(
                candidate.get("top_relevant_repos") or candidate.get("top_starred_repos", [])
            ),
        }

    def _signal_match_lines(self, signal_matches: List[Dict[str, Any]]) -> List[str]:
        lines = []

        for match in signal_matches[:8]:
            key = match.get("key")
            fields = ", ".join(match.get("matched_fields", []))
            if key and fields:
                lines.append(f"{key}: {fields}")
            elif key:
                lines.append(str(key))

        return lines

    def _notable_repositories(
        self,
        repositories: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        notable = []

        for repo in repositories[:3]:
            notable.append(
                {
                    "name": repo.get("name") or "Unknown",
                    "description": repo.get("description") or "Not listed",
                    "stars": repo.get("stars"),
                    "language": repo.get("language") or "Not listed",
                    "url": repo.get("url") or "",
                }
            )

        return notable

    def _limit_list(self, items: Any, limit: int) -> List[str]:
        if not isinstance(items, list):
            return []

        return [self._shorten(item, max_words=28) for item in items[:limit] if item]

    def _shorten(self, value: Any, max_words: int) -> str:
        text = str(value or "").strip()
        words = text.split()

        if len(words) <= max_words:
            return text

        return " ".join(words[:max_words]).rstrip(".,;:") + "..."
