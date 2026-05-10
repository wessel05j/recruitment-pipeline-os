import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.ai.candidate_advocate import CandidateAdvocate
from app.ai.candidate_skeptic import CandidateSkeptic
from app.ai.hiring_decision_manager import HiringDecisionManager


class CandidateReviewPanel:
    JOB_BRIEF_PATH = Path("app/temp/job_brief.txt")
    CANDIDATES_PATH = Path("app/temp/github_candidates.json")
    OUTPUT_DIR = Path("app/temp/candidate_reviews")

    def __init__(self, max_candidates: Optional[int] = None) -> None:
        self.max_candidates = max_candidates
        self.advocate = CandidateAdvocate()
        self.skeptic = CandidateSkeptic()
        self.manager = HiringDecisionManager()

    def run(self) -> List[Path]:
        job_brief = self._load_job_brief()
        candidates = self._load_candidates()

        if self.max_candidates:
            candidates = candidates[: self.max_candidates]

        output_paths = []

        for index, candidate in enumerate(candidates, start=1):
            existing_path = self._candidate_review_path(candidate)

            if existing_path.exists():
                print(
                    f"Skipping candidate {index}/{len(candidates)}: {candidate.get('username')} already reviewed"
                )
                output_paths.append(existing_path)
                continue

            print(f"Reviewing candidate {index}/{len(candidates)}: {candidate.get('username')}")

            review = self._review_candidate(job_brief, candidate)
            output_path = self._save_candidate_review(review)

            output_paths.append(output_path)

        return output_paths

    def _review_candidate(
        self,
        job_brief: str,
        candidate: Dict[str, Any],
    ) -> Dict[str, Any]:
        debate = {}
        previous_arguments = []

        for round_number in range(1, 4):
            advocate_argument = self.advocate.run(
                round_number=round_number,
                job_brief=job_brief,
                candidate=candidate,
                previous_arguments=previous_arguments,
            )

            clean_advocate_argument = self._without_metadata(advocate_argument)
            previous_arguments.append(clean_advocate_argument)

            skeptic_argument = self.skeptic.run(
                round_number=round_number,
                job_brief=job_brief,
                candidate=candidate,
                previous_arguments=previous_arguments,
            )

            clean_skeptic_argument = self._without_metadata(skeptic_argument)
            previous_arguments.append(clean_skeptic_argument)

            debate[f"round_{round_number}"] = {
                "advocate": clean_advocate_argument,
                "skeptic": clean_skeptic_argument,
            }

        decision = self.manager.run(
            job_brief=job_brief,
            candidate=candidate,
            debate=debate,
        )

        return {
            "candidate": candidate,
            "debate": debate,
            "decision": decision,
        }

    def _without_metadata(self, argument: Dict[str, Any]) -> Dict[str, Any]:
        return {
            key: value
            for key, value in argument.items()
            if key != "metadata"
        }

    def _load_job_brief(self) -> str:
        if not self.JOB_BRIEF_PATH.exists():
            raise FileNotFoundError(f"Missing job brief: {self.JOB_BRIEF_PATH}")

        return self.JOB_BRIEF_PATH.read_text(encoding="utf-8")

    def _load_candidates(self) -> List[Dict[str, Any]]:
        if not self.CANDIDATES_PATH.exists():
            raise FileNotFoundError(f"Missing candidates file: {self.CANDIDATES_PATH}")

        data = json.loads(self.CANDIDATES_PATH.read_text(encoding="utf-8"))

        if isinstance(data, list):
            return data

        if isinstance(data, dict) and "candidates" in data:
            return data["candidates"]

        raise ValueError("Invalid candidates JSON format.")

    def _save_candidate_review(self, review: Dict[str, Any]) -> Path:
        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        output_path = self._candidate_review_path(review["candidate"])

        with output_path.open("w", encoding="utf-8") as file:
            json.dump(review, file, ensure_ascii=False, indent=2)

        print(f"Saved review: {output_path}")
        return output_path

    def _candidate_review_path(self, candidate: Dict[str, Any]) -> Path:
        safe_username = "".join(
            char
            for char in candidate.get("username", "unknown")
            if char.isalnum() or char in ["-", "_"]
        )

        return self.OUTPUT_DIR / f"{safe_username}.json"
