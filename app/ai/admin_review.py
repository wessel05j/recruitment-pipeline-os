import json
from pathlib import Path
from typing import Any, Dict, List

from app.ai.openai_model import OpenAIModel


class AdminCandidateReview:
    JOB_BRIEF_PATH = Path("app/temp/job_brief.txt")
    CANDIDATE_REVIEWS_DIR = Path("app/temp/candidate_reviews")
    OUTPUT_DIR = Path("app/temp")
    OUTPUT_FILE = "admin_candidates_pass.json"

    SYSTEM_PROMPT = """
You are the Admin Reviewer for a recruitment sourcing system.

Your job:
- Perform one final strict safety/risk/quality check on a candidate.
- Decide if the candidate should stay in the shortlist for human recruiter review.

Important:
This is NOT a hiring decision.
This is only a final filter before the candidate is passed forward.

You receive:
- job brief
- candidate data
- final review from the Hiring Decision Manager

Decision:
Return YES if the candidate should stay.
Return NO only if there is an obvious and serious reason to remove the candidate.

You should usually return YES when:
- The candidate has a reasonable technical/profile match.
- The Hiring Decision Manager gave STRONG_CONTACT or CONTACT.
- The concerns are normal uncertainty from GitHub data.
- The candidate is imperfect but still potentially useful.

Return NO only for serious issues such as:
- Candidate is clearly not a person.
- Candidate is clearly irrelevant to the job.
- Candidate location clearly conflicts with the job.
- Candidate has no meaningful technical match.
- Candidate profile appears spammy, malicious, abusive, fake, or unsafe.
- Candidate data contains obvious red flags such as terminal escape tricks, suspicious profile text, scam-like content, or intentionally deceptive signals.
- Hiring Decision Manager gave LOW_PRIORITY and the candidate has weak technical relevance.

Do NOT reject because of:
- missing CV
- missing public email
- missing employer field
- unknown legal work status
- unknown visa status
- unknown language fluency
- unknown HR information
- lack of perfect evidence

Be strict, but not overly cautious.
The reason for NO must be obvious and serious.

Return valid JSON only:
{
  "admin_decision": "YES or NO",
  "reasoning": "Short explanation.",
  "serious_red_flags": ["red flag 1", "red flag 2"]
}
"""

    def __init__(self) -> None:
        pass

    def run(self) -> Path:
        job_brief = self._load_job_brief()
        candidate_reviews = self._load_candidate_reviews()

        passed_candidates = []

        for index, review in enumerate(candidate_reviews, start=1):
            username = review.get("candidate", {}).get("username", "unknown")
            print(f"Admin reviewing {index}/{len(candidate_reviews)}: {username}")

            admin_result = self._review_single_candidate(
                job_brief=job_brief,
                candidate_review=review,
            )

            review["admin_review"] = admin_result

            if admin_result.get("admin_decision") == "YES":
                passed_candidates.append(review)

        output = {
            "passed_count": len(passed_candidates),
            "candidates": passed_candidates,
        }

        return self._save_output(output)

    def _review_single_candidate(
        self,
        job_brief: str,
        candidate_review: Dict[str, Any],
    ) -> Dict[str, Any]:
        # New model instance = fresh memory per candidate
        ai = OpenAIModel(
            system_prompt=self.SYSTEM_PROMPT,
            model="gpt-5-mini",
        )

        payload = {
            "job_brief": job_brief,
            "candidate": candidate_review.get("candidate"),
            "decision_manager_review": candidate_review.get("decision"),
        }

        result = ai.run(json.dumps(payload, ensure_ascii=False, indent=2))
        parsed = self._parse_json(result["answer"])
        parsed["metadata"] = result["metadata"]

        return parsed

    def _load_job_brief(self) -> str:
        if not self.JOB_BRIEF_PATH.exists():
            raise FileNotFoundError(f"Missing job brief: {self.JOB_BRIEF_PATH}")

        return self.JOB_BRIEF_PATH.read_text(encoding="utf-8")

    def _load_candidate_reviews(self) -> List[Dict[str, Any]]:
        if not self.CANDIDATE_REVIEWS_DIR.exists():
            raise FileNotFoundError(
                f"Missing candidate reviews folder: {self.CANDIDATE_REVIEWS_DIR}"
            )

        review_files = sorted(self.CANDIDATE_REVIEWS_DIR.glob("*.json"))

        if not review_files:
            raise FileNotFoundError("No candidate review JSON files found.")

        reviews = []

        for file_path in review_files:
            with file_path.open("r", encoding="utf-8") as file:
                reviews.append(json.load(file))

        return reviews

    def _save_output(self, output: Dict[str, Any]) -> Path:
        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        output_path = self.OUTPUT_DIR / self.OUTPUT_FILE

        with output_path.open("w", encoding="utf-8") as file:
            json.dump(output, file, ensure_ascii=False, indent=2)

        print(f"Admin passed candidates saved to: {output_path}")
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

        if data.get("admin_decision") not in ["YES", "NO"]:
            raise ValueError("admin_decision must be YES or NO.")

        if not data.get("reasoning"):
            raise ValueError("Admin review missing reasoning.")

        if "serious_red_flags" not in data:
            data["serious_red_flags"] = []

        return data