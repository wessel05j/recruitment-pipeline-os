import json
from pathlib import Path
from typing import List, Optional

from app.sources.github import GitHubCandidateSearcher

class GitHubCandidateSearchRunner:
    '''Runs a GitHub candidate search and saves results to a JSON file.'''
    OUTPUT_DIR = Path("app/temp")
    OUTPUT_FILE = "github_candidates.json"

    def __init__(
        self,
        location: str,
        required_languages: List[str],
        signal_keys: Optional[List[str]] = None,
    ):
        self.location = location
        self.required_languages = required_languages
        self.signal_keys = signal_keys or []

        self._validate()

    def run(self) -> Path:
        searcher = GitHubCandidateSearcher()

        candidates = searcher.search(
            location=self.location,
            required_languages=self.required_languages,
            signal_keys=self.signal_keys,
        )
        funnel_metrics = searcher.get_funnel_metrics()

        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        output_path = self.OUTPUT_DIR / self.OUTPUT_FILE

        with output_path.open("w", encoding="utf-8") as file:
            json.dump(
                {
                    "location": self.location,
                    "required_languages": self.required_languages,
                    "signal_keys": self.signal_keys,
                    "funnel_metrics": funnel_metrics,
                    "candidate_count": len(candidates),
                    "candidates": candidates,
                },
                file,
                ensure_ascii=False,
                indent=2,
            )

        return output_path

    def _validate(self) -> None:
        if not self.location or not isinstance(self.location, str):
            raise ValueError("location is required and must be a string.")

        if not self.required_languages or not isinstance(self.required_languages, list):
            raise ValueError("required_languages is required and must be a non-empty list.")

        if not all(isinstance(lang, str) and lang.strip() for lang in self.required_languages):
            raise ValueError("Each required language must be a non-empty string.")

        if self.signal_keys and not all(isinstance(key, str) and key.strip() for key in self.signal_keys):
            raise ValueError("Each signal key must be a non-empty string.")
