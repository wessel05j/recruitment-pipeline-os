import os
import json
from dotenv import load_dotenv

from app.ai.account_manager import AccountManager
from app.ai.reqruitment_consultant import RecruitmentConsultant
from app.sources.github_search import GitHubCandidateSearchRunner
from app.ai.candidate_review import CandidateReviewPanel
from app.ai.admin_review import AdminCandidateReview


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
        search_params_path = "app/temp/github_search_params.json"
        if os.path.exists(search_params_path):
            print(f"Search parameters already exist at {search_params_path}. Skipping Recruitment Consultant.")
        else:
            print("Converting job brief into search parameters")
            consultant = RecruitmentConsultant()
            result = consultant.run()
            print(result["status"])
            if result["status"] == "APPROVED":
                print("Search parameters approved and saved.")
            else:
                print(result["message"])


        ###########################################################
        # Search Engine - GitHub search for candidates
        ###########################################################
        print("\n=== GitHub Search ===")
        candidates_path = "app/temp/github_candidates.json"
        if os.path.exists(candidates_path):
            print(f"Candidates already exist at {candidates_path}. Skipping GitHub search.")
        else:
            print("Takes up to 30 minutes.")
            with open(search_params_path, "r", encoding="utf-8") as file:
                search_params = json.load(file)
            location = search_params["location"]
            required_languages = search_params["required_languages"]
            bio_keys = search_params["bio_keys"]
            runner = GitHubCandidateSearchRunner(
                location=location,
                required_languages=required_languages,
                bio_keys=bio_keys,
            )
            runner.run()


        ###########################################################
        # Candidate review - Internal review of candidates
        ###########################################################
        print("\n=== Candidate Review ===")
        revew_path = "app/temp/candidate_reviews/"
        if os.path.exists(revew_path):
            print(f"Candidate review already exists at {revew_path}. Skipping Candidate Review.")
        else:
            panel = CandidateReviewPanel(max_candidates=1)
            review_paths = panel.run()
            
            for path in review_paths:
                print(f"Candidate review saved: {path}")


        ###########################################################
        # Admin review - final review
        ###########################################################
        print("\n=== Admin Review ===")
        admin = AdminCandidateReview()
        output_path = admin.run()

        print(f"Done: {output_path}")


        ###########################################################
        # Account Manager - Finalize
        ###########################################################


        ###########################################################
        # Export to PDF - Generate final report
        ###########################################################

        

    except Exception as e:
        print(f"Error in main loop: {e}")
        raise


if __name__ == "__main__":
    init()
    main()