import os
import json
from dotenv import load_dotenv

from app.ai.account_manager import AccountManager
from app.ai.reqruitment_consultant import RecruitmentConsultant
from app.sources.github_search import GitHubCandidateSearchRunner
from app.ai.candidate_review import CandidateReviewPanel
from app.ai.admin_review import AdminCandidateReview
from app.ai.candidate_format_builder import CandidateFormatBuilder
from app.reports.shortlist_pdf import ShortlistPDFGenerator


PROJECT_NAME = "recruitment-pipeline-os"
CREATOR = "Erich Johannes Wessel"
REPOSITORY_URL = "https://github.com/wessel05j/recruitment-pipeline-os"


def print_banner() -> None:
    line = "=" * 72
    print(line)
    print(f"{PROJECT_NAME} - GitHub candidate sourcing pipeline")
    print(f"Creator: {CREATOR}")
    print(f"Repository: {REPOSITORY_URL}")
    print(line)
    print("V1 focus: finding developer and IT candidates from public GitHub data.\n")


def print_section(title: str) -> None:
    print(f"\n--- {title} ---")


def print_skip(message: str) -> None:
    print(f"[skip] {message}")


def print_done(message: str) -> None:
    print(f"[done] {message}")


def init():
    load_dotenv()

    print("Checking environment...")

    required_env_vars = ["GITHUB_TOKEN", "OPENAI_API_KEY"]
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]

    if missing_vars:
        raise EnvironmentError(
            f"Missing environment variables: {', '.join(missing_vars)}"
        )

    print_done("Environment configured successfully.")


def main():
    try:
        print_banner()

        print_section("Account Manager")
        job_brief_path = "app/temp/job_brief.txt"
        if os.path.exists(job_brief_path):
            print_skip(f"Job brief already exists at {job_brief_path}.")
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
                    print_done("Job brief approved and saved.")
                    print(f"Path: {result['job_brief_path']}")
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
        print_section("Recruitment Consultant")
        search_params_path = "app/temp/github_search_params.json"
        if os.path.exists(search_params_path):
            print_skip(f"Search parameters already exist at {search_params_path}.")
        else:
            print("Converting job brief into search parameters")
            consultant = RecruitmentConsultant()
            result = consultant.run()
            print(result["status"])
            if result["status"] == "APPROVED":
                print_done("Search parameters approved and saved.")
            else:
                print(result["message"])


        ###########################################################
        # Search Engine - GitHub search for candidates
        ###########################################################
        print_section("GitHub Search")
        candidates_path = "app/temp/github_candidates.json"
        if os.path.exists(candidates_path):
            print_skip(f"Candidates already exist at {candidates_path}.")
        else:
            print("Takes up to 30 minutes.")
            with open(search_params_path, "r", encoding="utf-8") as file:
                search_params = json.load(file)
            location = search_params["location"]
            required_languages = search_params["required_languages"]
            signal_keys = search_params.get(
                "signal_keys",
                search_params.get("bio_keys", []),
            )
            runner = GitHubCandidateSearchRunner(
                location=location,
                required_languages=required_languages,
                signal_keys=signal_keys,
            )
            output_path = runner.run()
            print_done(f"GitHub candidates saved to {output_path}.")


        ###########################################################
        # Candidate review - Internal review of candidates
        ###########################################################
        print_section("Candidate Review")
        review_path = "app/temp/candidate_reviews/"
        if os.path.exists(review_path):
            print_skip(f"Candidate review already exists at {review_path}.")
        else:
            panel = CandidateReviewPanel(max_candidates=1)
            review_paths = panel.run()
            
            for path in review_paths:
                print_done(f"Candidate review saved: {path}")


        ###########################################################
        # Admin review - final review
        ###########################################################
        print_section("Admin Review")
        admin = AdminCandidateReview()
        output_path = admin.run()
        
        print_done(f"Admin review saved to {output_path}.")


        ###########################################################
        # Candidate Format Builder - report-ready candidate sections
        ###########################################################
        print_section("Candidate Format Builder")
        report_sections_path = "app/temp/candidate_report_sections.json"
        if os.path.exists(report_sections_path):
            print_skip(
                f"Candidate report sections already exist at {report_sections_path}."
            )
        else:
            formatter = CandidateFormatBuilder()
            output_path = formatter.run()
            print_done(f"Candidate report sections saved to {output_path}.")


        ###########################################################
        # Account Manager - Finalize
        ###########################################################


        ###########################################################
        # Export to PDF - Generate final report
        ###########################################################
        print_section("PDF Report")
        pdf_path = "app/output/github_candidate_shortlist.pdf"
        if os.path.exists(pdf_path):
            print_skip(f"PDF report already exists at {pdf_path}.")
        else:
            pdf = ShortlistPDFGenerator()
            output_path = pdf.run()
            print_done(f"PDF report saved to {output_path}.")

        print_section("Pipeline Complete")
        print_done("V1 pipeline finished.")
        print(f"Final PDF: {pdf_path}")
        print(f"Project: {REPOSITORY_URL}")

        

    except Exception as e:
        print(f"[error] {e}")
        raise


if __name__ == "__main__":
    init()
    main()
