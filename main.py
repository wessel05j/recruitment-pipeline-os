from app.sources.github_search import GitHubCandidateSearchRunner

runner = GitHubCandidateSearchRunner(
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
runner.run()