import json
from pathlib import Path
from typing import Dict, Any

from app.ai.openai_model import OpenAIModel


class AccountManager:
    OUTPUT_DIR = Path("app/temp")
    OUTPUT_FILE = "job_brief.txt"

    SYSTEM_PROMPT = """
You are an Account Manager at a recruitment firm.

Your job:
- Understand what kind of employee the company is looking for.
- Ask short follow-up questions if the information is not enough.
- If enough information is provided, create a structured job brief.

Tone:
- Professional, natural, concise.
- Sound like a real recruiter speaking to a client.
- Do not sound robotic.
- Do not over-explain.
- Do not be chatty.
- Ask only the most important missing questions, preferably 3–5 at a time.

Never say:
- "I can build the brief"
- "I can create the brief"
- "I can create a structured job brief"
- "I need more details"
- "clarifying questions"
- "more information is needed"

Instead, say things like:
- "Got it. To narrow the search, I need a few details:"
- "Understood. A few things will help define the role properly:"
- "That gives a starting point. To make the search accurate:"

You must eventually understand:
1. Job title / role
2. Country or location
3. Work setup: onsite, hybrid, remote
4. Seniority level
5. Required skills
6. Required programming languages or technologies, if relevant
7. Main responsibilities
8. Industry or company context
9. Employment type, if known
10. Nice-to-have skills
11. Any hard requirements

Decision rules:
- If important information is missing, return NEED_MORE_INFO.
- If enough information exists to define the role clearly, return APPROVED.
- Do not approve vague requests.
- Do not ask for everything at once unless almost everything is missing.
- Prioritize the next most useful questions.
- If the role is non-technical, do not force programming language questions.
- If the role is technical, ask for required technologies/tools.

Always respond as valid JSON only. No markdown. No extra text outside JSON.

JSON format when more info is needed:
{
  "status": "NEED_MORE_INFO",
  "reply": "Natural short response to the client. Ask the next best questions only.",
  "questions": [
    "Question 1",
    "Question 2",
    "Question 3"
  ]
}

JSON format when approved:
{
  "status": "APPROVED",
  "reply": "Approved. Job brief made.",
  "job_brief": "Full structured job brief here"
}

The job_brief should include:
- Role title
- Location
- Work setup
- Employment type
- Seniority
- Company / industry context
- Role summary
- Main responsibilities
- Required skills
- Required technologies/tools
- Nice-to-have skills
- Hard requirements
- Candidate search keywords
- Candidate exclusion criteria
"""

    INITIAL_MESSAGE = (
        "Tell us what kind of new employee you are looking for. "
        "Please include the role, location, required skills, technologies, seniority, "
        "work setup, and main responsibilities. The more details the better result."
    )

    def __init__(self) -> None:
        self.ai = OpenAIModel(
            system_prompt=self.SYSTEM_PROMPT,
            model="gpt-5-mini",
        )

    def get_initial_message(self) -> str:
        return self.INITIAL_MESSAGE

    def run(self, user_input: str) -> Dict[str, Any]:
        if not user_input or not user_input.strip():
            raise ValueError("user_input cannot be empty.")

        result = self.ai.run(user_input)
        raw_answer = result["answer"]

        parsed = self._parse_json(raw_answer)

        if parsed["status"] == "APPROVED":
            self._save_job_brief(parsed["job_brief"])

        return {
            "status": parsed["status"],
            "reply": parsed.get("reply"),
            "questions": parsed.get("questions", []),
            "job_brief_path": str(self.OUTPUT_DIR / self.OUTPUT_FILE)
            if parsed["status"] == "APPROVED"
            else None,
            "metadata": result["metadata"],
        }

    def _save_job_brief(self, job_brief: str) -> None:
        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        output_path = self.OUTPUT_DIR / self.OUTPUT_FILE

        with output_path.open("w", encoding="utf-8") as file:
            file.write(job_brief)

    def _parse_json(self, raw_answer: str) -> Dict[str, Any]:
        try:
            data = json.loads(raw_answer)
        except json.JSONDecodeError:
            raise ValueError(f"AI did not return valid JSON:\n{raw_answer}")

        if "status" not in data:
            raise ValueError("AI response missing 'status'.")

        if data["status"] not in ["NEED_MORE_INFO", "APPROVED"]:
            raise ValueError("Invalid AI status.")

        if data["status"] == "APPROVED" and not data.get("job_brief"):
            raise ValueError("Approved response missing job_brief.")

        return data