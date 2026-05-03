import os
from dotenv import load_dotenv

from app.ai.account_manager import AccountManager


def init():
    load_dotenv()

    print("Initializing the application...")

    required_env_vars = ["GITHUB_TOKEN", "OPENAI_API_KEY"]
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]

    if missing_vars:
        raise EnvironmentError(
            f"Missing environment variables: {', '.join(missing_vars)}"
        )

    print("Environment configured successfully.")


def main():
    try:
        print("Welcome to recruitment-pipeline-os!")
        print("Creator: Erich Johannes Wessel")
        print("Good luck on finding your next star employee!")
        account_manager = AccountManager()

        print("\n=== Account Manager ===")
        print(account_manager.get_initial_message())

        user_input = input("> ")

        while True:
            result = account_manager.run(user_input)

            metadata = result.get("metadata", {})
            context = metadata.get("context", {})
            context_used = context.get("context_used_percent")

            if result["status"] == "APPROVED":
                print("\nApproved. Job brief made")
                print(f"Saved to: {result['job_brief_path']}")
                break

            print("\n" + result["reply"])

            for question in result["questions"]:
                print(f"- {question}")

            if context_used is not None:
                user_input = input(f"{context_used}%> ")
            else:
                user_input = input("> ")

    except Exception as e:
        print(f"Error in main loop: {e}")
        raise


if __name__ == "__main__":
    init()
    main()