import os
from dotenv import load_dotenv

from app.ai.account_manager import AccountManager
from app.ai.reqruitment_consultant import RecruitmentConsultant

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
        print("Good luck on finding your next star employee!\n")

        print("\n=== Account Manager ===")
        job_brief_path = "app/temp/job_brief.txt"
        if os.path.exists(job_brief_path):
            print(f"Job brief already exists at {job_brief_path}. Skipping Account Manager.")
        else:
            ###########################################################
            # Account Manager - Initial conversation with client
            ###########################################################
            account_manager = AccountManager()
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
        

        ###########################################################
        # Recruitment Consultant - Candidate sourcing
        ###########################################################
        print("\n=== Recruitment Consultant ===")
        print("Converting job brief into search parameters")
        consultant = RecruitmentConsultant()
        result = consultant.run()
        print(result["status"])
        if result["status"] == "APPROVED":
            print(f"Location: {result['location']}")
            print(f"Required languages: {result['required_languages']}")
            print(f"Bio keys: {result['bio_keys']}")
        else:
            print(result["message"])

        ###########################################################
        # Candidate review - Internal review of candidates
        ###########################################################



        ###########################################################
        # Admin review - final review
        ###########################################################



        ###########################################################
        # Account Manager - Finalize job brief
        ###########################################################

        

    except Exception as e:
        print(f"Error in main loop: {e}")
        raise


if __name__ == "__main__":
    init()
    main()