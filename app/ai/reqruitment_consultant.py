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
    - signal_keys: list[str]
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
3. signal_keys: list of high-signal single-word keywords likely to appear in GitHub bios or repository metadata.

Rules:
- Return valid JSON only.
- Do not include markdown.
- Always return APPROVED.
- Do not ask follow-up questions.
- Do not return NEED_MORE_INFO.
- Do not return NOT_SUITABLE.
- Use the best possible values from the job brief.
- If something is imperfect, make the safest useful choice.
- required_languages must only contain actual programming languages.
- location must be one clear location. If the job says Norway, use "Norway". If it says Oslo, use "Oslo".

Signal key strategy:
- Return 8–20 signal_keys.
- Quality over quantity.
- Every signal_key must be exactly ONE word.
- Signal keys must be optimized for GitHub profile bios, repository names, repository descriptions, and repository topics, not job descriptions.
- Prefer keywords that a relevant candidate might realistically use to describe themselves, their specialty, their tooling, or their domain.
- Prefer terms that identify candidates with matching public projects or technical identity.
- Avoid filler. If only 8 strong keys exist, return 8.

Signal key selection order:
1. Include the strongest single-word role identity keywords from the job brief.
   - These are words that describe what the candidate does professionally.
   - They are allowed even if somewhat broad, as long as they are central to the role.
   - Examples: "Automation", "RPA", "DevOps", "Security", "Data", "ML", "Backend".
2. Include high-signal technical ecosystem keywords.
   - Examples: "pandas", "openpyxl", "UiPath", "PowerAutomate", "Spark", "Kubernetes".
3. Include strong domain keywords only when the domain is central to the role.
   - Examples: "Accounting", "Finance", "ERP", "Healthcare", "Cybersecurity".
4. Include product/vendor/platform keywords only when they are explicit useful signals.
   - Examples: "Tripletex", "Visma", "Dynamics", "Salesforce", "SAP".
5. Exclude words that are relevant to the job but unlikely to be useful in a GitHub bio.

Important distinction:
- Do not reject a word just because it is broad.
- Reject broad words only when they are generic across most software candidates.
- A broad word is acceptable if it is the central specialization of the role.
- For example, "Automation" is good for an automation/RPA role.
- "Developer" is bad because it matches almost everyone.
- "Finance" is acceptable only when finance/accounting domain experience is central.
- "Git" is bad because almost every GitHub user has Git.

Do not include:
- Generic role words: "Developer", "Engineer", "Programmer", "Software", "Tech", "IT", "Coding".
- Generic soft-skill words: "professional", "motivated", "team", "communication", "problem", "passionate".
- Seniority, years of experience, employment type, or location.
- Broad engineering hygiene terms: "Git", "Testing", "Documentation", "Logging", "CleanCode", "BestPractices".
- Low-signal implementation details: "JSON", "HTTP", "REST", "requests", "scripts", "utilities", "validation", "parsing".
- Programming languages in signal_keys unless the word is also a meaningful role/domain identity.
- Multi-word phrases.

Conversion rules:
- Convert multi-word concepts into the strongest single-word equivalent.
- "RPA Developer" -> "RPA"
- "Automation Developer" -> "Automation"
- "Finance Automation" -> "Finance" and/or "Automation"
- "Accounting Automation" -> "Accounting" and/or "Automation"
- "Power Automate" -> "PowerAutomate"
- "Dynamics 365" -> "Dynamics"
- "Excel automation" -> "Excel" and/or "Automation"
- "CSV processing" -> "CSV" only if CSV/Excel processing is central
- "API integration" -> usually exclude "API" unless integrations are a major sourcing signal

Good signal_keys examples:
- "Automation"
- "RPA"
- "Excel"
- "CSV"
- "pandas"
- "openpyxl"
- "UiPath"
- "PowerAutomate"
- "ETL"
- "Accounting"
- "Finance"
- "ERP"
- "Tripletex"
- "Visma"
- "Dynamics"

Bad signal_keys examples:
- "Automation Developer"
- "Finance Automation"
- "Accounting Automation"
- "Software Engineer"
- "Developer"
- "Engineer"
- "Norway"
- "Remote"
- "Junior"
- "Git"
- "requests"
- "JSON"
- "problem solving"

Before returning, silently check:
- Are all signal_keys one word?
- Are there 8–20 signal_keys?
- Did I include the strongest role identity keywords when they are central?
- Did I avoid generic software words?
- Did I avoid implementation details that are unlikely to appear in bios?
- Would each bio_key help find a better candidate rather than just more candidates?

JSON format example:
{
  "status": "APPROVED",
  "source": "github",
  "location": "Norway",
  "required_languages": ["Python"],
  "signal_keys": ["Automation", "RPA", "Excel", "pandas", "openpyxl", "UiPath", "PowerAutomate", "ETL", "Accounting", "Tripletex", "Visma"],
  "reasoning": "Chosen for a Python-focused automation role in Norway. The signal keys prioritize central role identity, relevant automation tooling, data workflow skills, and accounting/ERP domain signals while avoiding generic software terms and low-signal implementation details."
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

        if "signal_keys" not in data and "bio_keys" in data:
            data["signal_keys"] = data.pop("bio_keys")

        if not data.get("location") or not isinstance(data["location"], str):
            raise ValueError("location must be a string.")

        if not data.get("required_languages") or not isinstance(data["required_languages"], list):
            raise ValueError("required_languages must be a non-empty list.")

        if not all(isinstance(lang, str) and lang.strip() for lang in data["required_languages"]):
            raise ValueError("Each required language must be a non-empty string.")

        if not data.get("signal_keys") or not isinstance(data["signal_keys"], list):
            raise ValueError("signal_keys must be a non-empty list.")

        if not all(isinstance(key, str) and key.strip() for key in data["signal_keys"]):
            raise ValueError("Each signal key must be a non-empty string.")

        if len(data["signal_keys"]) > 20:
            raise ValueError("signal_keys should not contain more than 20 items.")
