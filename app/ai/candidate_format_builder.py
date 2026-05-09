import json
from pathlib import Path
from typing import Any, Dict

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
- Keep text client-ready, concise, and factual.

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
