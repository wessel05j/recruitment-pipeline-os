from app.ai.openai_model import OpenAIModel


def main() -> None:
    ai = OpenAIModel(
        system_prompt="You are a strict and concise recruitment assistant.",
        model="gpt-5-mini",
    )

    result = ai.run(
        "Explain why GitHub can be useful for finding developer candidates."
    )

    print(result["answer"])
    print(result["metadata"])


if __name__ == "__main__":
    main()