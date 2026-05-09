import json
from datetime import datetime, timezone
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
- contactability score and routes from the Hiring Decision Manager

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
- low contactability when the technical match is otherwise useful
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

        ranked_candidates = self._rank_passed_candidates(passed_candidates)

        output = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "passed_count": len(ranked_candidates),
            "candidates": ranked_candidates,
        }

        return self._save_output(output)

    def _rank_passed_candidates(
        self,
        candidate_reviews: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        sorted_reviews = sorted(
            candidate_reviews,
            key=self._candidate_score,
            reverse=True,
        )

        return [
            self._build_ranked_candidate(rank=index, review=review)
            for index, review in enumerate(sorted_reviews, start=1)
        ]

    def _candidate_score(self, review: Dict[str, Any]) -> int:
        score = review.get("decision", {}).get("final_score", 0)

        if isinstance(score, int):
            return score

        try:
            return int(score)
        except (TypeError, ValueError):
            return 0

    def _build_ranked_candidate(
        self,
        rank: int,
        review: Dict[str, Any],
    ) -> Dict[str, Any]:
        candidate = review.get("candidate", {})
        decision = review.get("decision", {})
        admin_review = review.get("admin_review", {})

        return {
            "rank": rank,
            "candidate": self._candidate_summary(candidate),
            "assessment": self._assessment_summary(decision),
            "admin_review": {
                "admin_decision": admin_review.get("admin_decision"),
                "reasoning": admin_review.get("reasoning"),
                "serious_red_flags": admin_review.get("serious_red_flags", []),
            },
        }

    def _candidate_summary(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "name": candidate.get("name"),
            "username": candidate.get("username"),
            "bio": candidate.get("bio"),
            "company": candidate.get("company"),
            "location": candidate.get("location"),
            "blog_url": candidate.get("blog_url"),
            "email": candidate.get("email"),
            "twitter_username": candidate.get("twitter_username"),
            "repo_count": candidate.get("repo_count"),
            "followers": candidate.get("followers"),
            "following": candidate.get("following"),
            "account_created": candidate.get("account_created"),
            "last_profile_update": candidate.get("last_profile_update"),
            "github_profile_url": candidate.get("github_profile_url"),
            "avatar_url": candidate.get("avatar_url"),
            "matched_languages": candidate.get("matched_languages", []),
            "language_counts": candidate.get("language_counts", {}),
            "latest_repo_push": candidate.get("latest_repo_push"),
            "signal_keys": candidate.get("signal_keys", []),
            "signal_matches": candidate.get("signal_matches", []),
            "top_starred_repos": candidate.get("top_starred_repos", []),
        }

    def _assessment_summary(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "final_score": decision.get("final_score"),
            "recommendation": decision.get("recommendation"),
            "summary": decision.get("summary"),
            "key_strengths": decision.get("key_strengths", []),
            "key_concerns": decision.get("key_concerns", []),
            "contactability_score": decision.get("contactability_score"),
            "contactability_label": decision.get("contactability_label"),
            "contactability_reason": decision.get("contactability_reason"),
            "contact_routes": decision.get("contact_routes", []),
            "contact_research_clues": decision.get("contact_research_clues", []),
        }

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
