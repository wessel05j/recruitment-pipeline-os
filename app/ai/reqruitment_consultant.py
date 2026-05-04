import json
from pathlib import Path
from typing import Any, Dict

from app.ai.openai_model import OpenAIModel


class RecruitmentConsultant:
    """
    Converts a structured job brief into source-search parameters.

    Current supported source:
    - GitHub

    Output:
    - location: str
    - required_languages: list[str]
    - bio_keys: list[str]
    """

    INPUT_PATH = Path("app/temp/job_brief.txt")
    OUTPUT_DIR = Path("app/temp")
    OUTPUT_FILE = "github_search_params.json"

    SYSTEM_PROMPT = """
You are a Recruitment Consultant specialized in candidate sourcing.

Your job is to convert a completed structured job brief into search parameters for the available sourcing tools.

Available source tools:
GitHubCandidateSearcher

GitHubCandidateSearcher requires:
1. location: exactly one country or city string.
2. required_languages: list of programming languages only.
3. bio_keys: list of quality keywords likely to appear in serious GitHub bios.

Rules:
- Return valid JSON only.
- Do not include markdown.
- Always return APPROVED.
- Do not ask follow-up questions.
- Do not return NEED_MORE_INFO.
- Do not return NOT_SUITABLE.
- Use the best possible values from the job brief.
- If something is imperfect, make the safest useful choice.
- Prefer more bio keys.
- Try to always get 10 proper bio keys.
- bio_keys should be useful for finding candidates, not generic filler.
- required_languages must only contain actual programming languages.
- Do not include tools like OpenAI API, LangChain, Docker, AWS, React, PostgreSQL in required_languages.
- Put important tools/frameworks/concepts in bio_keys if useful.
- Do not put programming languages in bio_keys unless they are also a role identity.
- location must be one clear location. If the job says Norway, use "Norway". If it says Oslo, use "Oslo".

Good bio_keys examples:
- "LLM"
- "OpenAI"
- "Prompt Engineering"
- "AI Engineer"
- "Machine Learning"
- "Cybersecurity"
- "Backend"
- "Data Science"
- "Full Stack"

Bad bio_keys examples:
- "professional"
- "motivated"
- "team player"
- "communication"
- "problem solving"
- "5 years"
- "Norway"
- "onsite"

JSON format example:
{
  "status": "APPROVED",
  "source": "github",
  "location": "Norway",
  "required_languages": ["Python"],
  "bio_keys": ["LLM", "OpenAI", "Prompt Engineering", "AI Engineer", "Machine Learning"],
  "reasoning": "Short explanation of why these search parameters were chosen."
}
"""

    def __init__(self) -> None:
        self.ai = OpenAIModel(
            system_prompt=self.SYSTEM_PROMPT,
            model="gpt-5-mini",
        )

    def run(self, job_brief: str | None = None) -> Dict[str, Any]:
        job_brief = job_brief or self._load_job_brief()

        if not job_brief.strip():
            raise ValueError("job_brief cannot be empty.")

        result = self.ai.run(job_brief)
        parsed = self._parse_json(result["answer"])

        if parsed["status"] == "APPROVED":
            self._save_search_params(parsed)

        return {
            **parsed,
            "metadata": result["metadata"],
            "output_path": str(self.OUTPUT_DIR / self.OUTPUT_FILE)
            if parsed["status"] == "APPROVED"
            else None,
        }

    def _load_job_brief(self) -> str:
        if not self.INPUT_PATH.exists():
            raise FileNotFoundError(f"Missing job brief: {self.INPUT_PATH}")

        return self.INPUT_PATH.read_text(encoding="utf-8")

    def _save_search_params(self, data: Dict[str, Any]) -> None:
        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        output_path = self.OUTPUT_DIR / self.OUTPUT_FILE

        with output_path.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)

    def _parse_json(self, raw_answer: str) -> Dict[str, Any]:
        try:
            data = json.loads(raw_answer)
        except json.JSONDecodeError:
            raise ValueError(f"AI did not return valid JSON:\n{raw_answer}")

        if data.get("status") != "APPROVED":
            raise ValueError("RecruitmentConsultant must always return APPROVED.")

        self._validate_approved(data)
        return data

    def _validate_approved(self, data: Dict[str, Any]) -> None:
        if data.get("source") != "github":
            raise ValueError("source must be 'github'.")

        if not data.get("location") or not isinstance(data["location"], str):
            raise ValueError("location must be a string.")

        if not data.get("required_languages") or not isinstance(data["required_languages"], list):
            raise ValueError("required_languages must be a non-empty list.")

        if not all(isinstance(lang, str) and lang.strip() for lang in data["required_languages"]):
            raise ValueError("Each required language must be a non-empty string.")

        if not data.get("bio_keys") or not isinstance(data["bio_keys"], list):
            raise ValueError("bio_keys must be a non-empty list.")

        if not all(isinstance(key, str) and key.strip() for key in data["bio_keys"]):
            raise ValueError("Each bio key must be a non-empty string.")

        if len(data["bio_keys"]) > 10:
            raise ValueError("bio_keys should not contain more than 10 items.")