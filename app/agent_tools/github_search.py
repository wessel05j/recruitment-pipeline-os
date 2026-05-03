from app.sources.github import GitHubCandidateSearcher


def main() -> None:
    searcher = GitHubCandidateSearcher()

    candidates = searcher.search(
        location="Norway",
        required_languages=["JavaScript"],
        bio_keys=[
            "AI",
            "Artificial Intelligence",
            "Machine Learning",
            "ML",
            "Cybersecurity",
            "Security",
            "Data Science",
            "Backend",
            "Full Stack",
            "Software Engineer",
        ],
    )

    print(f"Found {len(candidates)} candidates")

    for candidate in candidates:
        print("-" * 60)
        print(f"Name: {candidate['name']}")
        print(f"Username: {candidate['username']}")
        print(f"Bio: {candidate['bio']}")
        print(f"Company: {candidate['company']}")
        print(f"Location: {candidate['location']}")
        print(f"Email: {candidate['email']}")
        print(f"GitHub: {candidate['github_profile_url']}")
        print(f"Languages: {candidate['language_counts']}")
        print(f"Latest push: {candidate['latest_repo_push']}")


if __name__ == "__main__":
    main()