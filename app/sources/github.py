import os
import re
import time
from datetime import datetime, timedelta, timezone
from collections import Counter
from typing import Any, Dict, List, Optional, Set

import requests
from dotenv import load_dotenv

load_dotenv()


class GitHubCandidateSearcher:
    BASE_URL = "https://api.github.com"

    MIN_REPOS = 2
    MIN_FOLLOWERS = 2
    RECENT_ACTIVITY_DAYS = 90
    LIMIT_PER_PAGE = 100
    MAX_SEARCH_PAGES_PER_LANGUAGE = 10  # GitHub max = 1000 search results
    MAX_CANDIDATES = 20
    TOP_STARRED_REPOS_LIMIT = 10
    SIGNAL_REPO_SCAN_LIMIT = 20
    REQUIRE_EMAIL = False
    REQUIRE_FULL_NAME = False

    def __init__(
        self,
        token: Optional[str] = None,
        timeout: int = 20,
        sleep_between_requests: float = 0.2,
    ):
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.timeout = timeout
        self.sleep_between_requests = sleep_between_requests
        self.funnel_metrics: Counter[str] = Counter()

        if not self.token:
            raise ValueError(
                "Missing GitHub token. Pass token=... or set GITHUB_TOKEN in environment."
            )

        self.headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def search(
        self,
        location: str,
        required_languages: List[str],
        signal_keys: Optional[List[str]] = None,
        bio_keys: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        if signal_keys is None and bio_keys is not None:
            signal_keys = bio_keys

        self._validate_search_input(location, required_languages, signal_keys)

        self.funnel_metrics = Counter()
        signal_keys = signal_keys or []
        candidate_pool: List[Dict[str, Any]] = []
        checked_usernames: Set[str] = set()

        for language in required_languages:
            for page in range(1, self.MAX_SEARCH_PAGES_PER_LANGUAGE + 1):
                users = self._search_user_page(
                    location=location,
                    language=language,
                    page=page,
                )
                self.funnel_metrics["search_pages_requested"] += 1
                self.funnel_metrics["users_returned"] += len(users)

                if not users:
                    break

                for user in users:
                    username = user.get("login")

                    if not username:
                        self.funnel_metrics["skipped_missing_username"] += 1
                        continue

                    if username in checked_usernames:
                        self.funnel_metrics["skipped_duplicate_username"] += 1
                        continue

                    checked_usernames.add(username)

                    if user.get("type") != "User":
                        self.funnel_metrics["skipped_non_user"] += 1
                        continue

                    candidate = self._process_candidate(
                        username=username,
                        location=location,
                        required_languages=required_languages,
                        signal_keys=signal_keys,
                    )

                    if candidate:
                        candidate_pool.append(candidate)
                        self.funnel_metrics["candidate_pool_candidates"] += 1

        ranked_candidates = self._rank_candidates(candidate_pool)
        self.funnel_metrics["ranked_candidate_pool"] = len(ranked_candidates)
        self.funnel_metrics["returned_candidates"] = min(
            len(ranked_candidates),
            self.MAX_CANDIDATES,
        )
        return ranked_candidates[: self.MAX_CANDIDATES]

    def _validate_search_input(
        self,
        location: str,
        required_languages: List[str],
        signal_keys: Optional[List[str]],
    ) -> None:
        if not location or not isinstance(location, str):
            raise ValueError("location is required and must be a string.")

        if not required_languages or not isinstance(required_languages, list):
            raise ValueError("required_languages is required and must be a non-empty list.")

        if not all(isinstance(lang, str) and lang.strip() for lang in required_languages):
            raise ValueError("Each required language must be a non-empty string.")

        if signal_keys is not None:
            if not isinstance(signal_keys, list):
                raise ValueError("signal_keys must be a list if provided.")

            if not all(isinstance(key, str) and key.strip() for key in signal_keys):
                raise ValueError("Each signal key must be a non-empty string.")

    def _search_user_page(
        self,
        location: str,
        language: str,
        page: int,
    ) -> List[Dict[str, Any]]:
        query = " ".join(
            [
                f"location:{self._format_search_value(location)}",
                f"language:{self._format_search_value(language)}",
                f"repos:>={self.MIN_REPOS}",
                f"followers:>={self.MIN_FOLLOWERS}",
            ]
        )

        data = self._get(
            "/search/users",
            params={
                "q": query,
                "per_page": self.LIMIT_PER_PAGE,
                "page": page,
            },
        )

        return data.get("items", [])

    def _process_candidate(
        self,
        username: str,
        location: str,
        required_languages: List[str],
        signal_keys: List[str],
    ) -> Optional[Dict[str, Any]]:
        self.funnel_metrics["users_considered"] += 1

        repos = self._fetch_user_repos(username)

        if not repos:
            self.funnel_metrics["failed_no_repositories"] += 1
            return None

        language_counts = self._count_repo_languages(repos)

        if not self._has_all_required_languages(language_counts, required_languages):
            self.funnel_metrics["failed_required_languages"] += 1
            return None

        self.funnel_metrics["passed_required_languages"] += 1
        profile = self._fetch_user_profile(username)
        signal_matches = self._find_signal_matches(
            profile=profile,
            repos=repos,
            signal_keys=signal_keys,
        )

        failure_reason = self._profile_filter_failure(
            profile=profile,
            signal_keys=signal_keys,
            signal_matches=signal_matches,
        )

        if failure_reason:
            self.funnel_metrics[f"failed_{failure_reason}"] += 1
            return None

        self.funnel_metrics["passed_signal_keys"] += 1
        source_fit = self._source_fit(
            profile=profile,
            repos=repos,
            location=location,
            required_languages=required_languages,
            signal_matches=signal_matches,
        )

        profile["matched_languages"] = sorted(language_counts.keys())
        profile["language_counts"] = language_counts
        profile["latest_repo_push"] = self._latest_repo_push(repos)
        profile["signal_keys"] = signal_keys
        profile["signal_matches"] = signal_matches
        profile["signal_match_count"] = len(signal_matches)
        profile["source_fit_score"] = source_fit["score"]
        profile["source_fit_breakdown"] = source_fit["breakdown"]
        profile["source_fit_reasons"] = source_fit["reasons"]
        profile["top_relevant_repos"] = self._top_relevant_repos(
            repos=repos,
            signal_matches=signal_matches,
            limit=5,
        )
        profile["top_starred_repos"] = self._top_starred_repos(
            repos=repos,
            limit=self.TOP_STARRED_REPOS_LIMIT,
        )

        return profile

    def _rank_candidates(
        self,
        candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        return sorted(
            candidates,
            key=lambda candidate: (
                candidate.get("source_fit_score", 0),
                candidate.get("signal_match_count", 0),
                candidate.get("latest_repo_push") or "",
            ),
            reverse=True,
        )

    def get_funnel_metrics(self) -> Dict[str, int]:
        return dict(self.funnel_metrics)

    def _format_search_value(self, value: str) -> str:
        cleaned = value.strip().replace('"', '\\"')

        if re.search(r"\s", cleaned):
            return f'"{cleaned}"'

        return cleaned

    def _fetch_user_profile(self, username: str) -> Dict[str, Any]:
        data = self._get(f"/users/{username}")

        return {
            "name": data.get("name"),
            "username": data.get("login"),
            "bio": data.get("bio"),
            "company": data.get("company"),
            "location": data.get("location"),
            "blog_url": data.get("blog"),
            "email": data.get("email"),
            "twitter_username": data.get("twitter_username"),
            "repo_count": data.get("public_repos"),
            "followers": data.get("followers"),
            "following": data.get("following"),
            "account_created": data.get("created_at"),
            "last_profile_update": data.get("updated_at"),
            "github_profile_url": data.get("html_url"),
            "avatar_url": data.get("avatar_url"),
        }

    def _fetch_user_repos(self, username: str) -> List[Dict[str, Any]]:
        return self._get(
            f"/users/{username}/repos",
            params={
                "per_page": 100,
                "sort": "pushed",
                "direction": "desc",
            },
        )

    def _top_starred_repos(
        self,
        repos: List[Dict[str, Any]],
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        sorted_repos = sorted(
            repos,
            key=lambda repo: repo.get("stargazers_count", 0),
            reverse=True,
        )

        top_repos = []

        for repo in sorted_repos[:limit]:
            top_repos.append(
                {
                    "name": repo.get("name"),
                    "description": repo.get("description"),
                    "stars": repo.get("stargazers_count"),
                    "forks": repo.get("forks_count"),
                    "language": repo.get("language"),
                    "url": repo.get("html_url"),
                    "updated_at": repo.get("updated_at"),
                    "pushed_at": repo.get("pushed_at"),
                }
            )

        return top_repos

    def _top_relevant_repos(
        self,
        repos: List[Dict[str, Any]],
        signal_matches: List[Dict[str, Any]],
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        match_index: Dict[str, Dict[str, Set[str]]] = {}

        for match in signal_matches:
            key = match.get("key")
            if not key:
                continue

            for repo_hit in match.get("repositories", []):
                repo_name = repo_hit.get("name")
                if not repo_name:
                    continue

                entry = match_index.setdefault(
                    repo_name,
                    {"keys": set(), "fields": set()},
                )
                entry["keys"].add(key)
                entry["fields"].update(repo_hit.get("matched_fields", []))

        relevant_repos = []

        for repo in repos:
            repo_name = repo.get("name")
            if repo_name not in match_index:
                continue

            matched = match_index[repo_name]
            relevant_repos.append(
                {
                    "name": repo.get("name"),
                    "description": repo.get("description"),
                    "stars": repo.get("stargazers_count"),
                    "forks": repo.get("forks_count"),
                    "language": repo.get("language"),
                    "url": repo.get("html_url"),
                    "updated_at": repo.get("updated_at"),
                    "pushed_at": repo.get("pushed_at"),
                    "matched_signal_keys": sorted(matched["keys"]),
                    "matched_fields": sorted(matched["fields"]),
                    "relevance_score": self._repo_relevance_score(repo, matched),
                }
            )

        return sorted(
            relevant_repos,
            key=lambda repo: (
                repo.get("relevance_score", 0),
                repo.get("pushed_at") or "",
            ),
            reverse=True,
        )[:limit]

    def _count_repo_languages(self, repos: List[Dict[str, Any]]) -> Dict[str, int]:
        counts: Dict[str, int] = {}

        for repo in repos:
            language = repo.get("language")

            if not language:
                continue

            counts[language] = counts.get(language, 0) + 1

        return counts

    def _has_all_required_languages(
        self,
        language_counts: Dict[str, int],
        required_languages: List[str],
    ) -> bool:
        found = {lang.lower() for lang in language_counts.keys()}
        required = {lang.lower() for lang in required_languages}

        return required.issubset(found)

    def _has_recent_repo_activity(self, repos: List[Dict[str, Any]]) -> bool:
        latest_push = self._latest_repo_push(repos)

        if not latest_push:
            return False

        cutoff = datetime.now(timezone.utc) - timedelta(days=self.RECENT_ACTIVITY_DAYS)
        latest_push_date = datetime.fromisoformat(latest_push.replace("Z", "+00:00"))

        return latest_push_date >= cutoff

    def _latest_repo_push(self, repos: List[Dict[str, Any]]) -> Optional[str]:
        pushed_dates = [repo.get("pushed_at") for repo in repos if repo.get("pushed_at")]

        if not pushed_dates:
            return None

        return max(pushed_dates)

    def _source_fit(
        self,
        profile: Dict[str, Any],
        repos: List[Dict[str, Any]],
        location: str,
        required_languages: List[str],
        signal_matches: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        signal_score = self._signal_score(signal_matches)
        relevant_repo_count = self._relevant_repo_count(signal_matches)
        repo_evidence_score = self._repo_evidence_score(relevant_repo_count)
        recency_score = self._recency_score(self._latest_repo_push(repos))
        location_score = self._location_score(profile.get("location"), location)

        breakdown = {
            "required_language": 30,
            "signal_relevance": signal_score,
            "repo_evidence": repo_evidence_score,
            "recent_activity": recency_score,
            "location": location_score,
        }
        score = min(100, sum(breakdown.values()))
        reasons = [
            f"Required language match: {', '.join(required_languages)}.",
            f"Matched {len(signal_matches)} distinct signal keys.",
            f"Found signal evidence in {relevant_repo_count} repositories.",
        ]

        latest_push = self._latest_repo_push(repos)
        if latest_push:
            reasons.append(f"Latest public repo push: {latest_push}.")

        if location_score:
            reasons.append(f"Profile location matched search location: {location}.")

        return {
            "score": score,
            "breakdown": breakdown,
            "reasons": reasons,
        }

    def _signal_score(self, signal_matches: List[Dict[str, Any]]) -> int:
        field_weights = {
            "repo_topics": 8,
            "repo_name": 7,
            "repo_description": 6,
            "bio": 5,
        }
        score = 0

        for match in signal_matches:
            fields = match.get("matched_fields", [])
            key_score = max((field_weights.get(field, 0) for field in fields), default=0)
            repository_bonus = min(len(match.get("repositories", [])), 3)
            score += key_score + repository_bonus

        return min(score, 40)

    def _relevant_repo_count(self, signal_matches: List[Dict[str, Any]]) -> int:
        repo_names = set()

        for match in signal_matches:
            for repo in match.get("repositories", []):
                if repo.get("name"):
                    repo_names.add(repo["name"])

        return len(repo_names)

    def _repo_evidence_score(self, relevant_repo_count: int) -> int:
        if relevant_repo_count >= 4:
            return 15

        if relevant_repo_count == 3:
            return 12

        if relevant_repo_count == 2:
            return 9

        if relevant_repo_count == 1:
            return 5

        return 0

    def _recency_score(self, latest_push: Optional[str]) -> int:
        if not latest_push:
            return 0

        latest_push_date = datetime.fromisoformat(latest_push.replace("Z", "+00:00"))
        age_days = (datetime.now(timezone.utc) - latest_push_date).days

        if age_days <= 30:
            return 10

        if age_days <= 90:
            return 7

        if age_days <= 180:
            return 4

        return 1

    def _location_score(
        self,
        profile_location: Optional[str],
        search_location: str,
    ) -> int:
        if not profile_location:
            return 0

        profile_location_lower = profile_location.lower()
        search_terms = [
            term.lower()
            for term in re.split(r"[\s,]+", search_location)
            if len(term.strip()) >= 3
        ]

        if any(term in profile_location_lower for term in search_terms):
            return 5

        return 0

    def _repo_relevance_score(
        self,
        repo: Dict[str, Any],
        matched: Dict[str, Set[str]],
    ) -> int:
        field_weights = {
            "topics": 5,
            "name": 4,
            "description": 3,
        }
        score = len(matched["keys"]) * 3
        score += sum(field_weights.get(field, 0) for field in matched["fields"])

        if repo.get("description"):
            score += 1

        if repo.get("pushed_at"):
            score += 1

        return score

    def _profile_filter_failure(
        self,
        profile: Dict[str, Any],
        signal_keys: List[str],
        signal_matches: List[Dict[str, Any]],
    ) -> Optional[str]:
        if self.REQUIRE_FULL_NAME and not self._has_full_name(profile.get("name")):
            return "full_name"

        if self.REQUIRE_EMAIL and not profile.get("email"):
            return "email"

        if signal_keys and not signal_matches:
            return "signal_keys"

        return None

    def _has_full_name(self, name: Optional[str]) -> bool:
        if not name:
            return False

        words = name.strip().split()

        if not 2 <= len(words) <= 4:
            return False

        for word in words:
            if not re.match(r"^[A-Za-zÀ-ÖØ-öø-ÿ'-]{2,}$", word):
                return False

        return True

    def _find_signal_matches(
        self,
        profile: Dict[str, Any],
        repos: List[Dict[str, Any]],
        signal_keys: List[str],
    ) -> List[Dict[str, Any]]:
        matches: List[Dict[str, Any]] = []

        for key in signal_keys:
            key_lower = key.lower()
            fields: Set[str] = set()
            repo_hits = []

            if key_lower in (profile.get("bio") or "").lower():
                fields.add("bio")

            for repo in repos[: self.SIGNAL_REPO_SCAN_LIMIT]:
                repo_fields = []

                if key_lower in (repo.get("name") or "").lower():
                    repo_fields.append("name")

                if key_lower in (repo.get("description") or "").lower():
                    repo_fields.append("description")

                topics = repo.get("topics") or []
                if any(key_lower in topic.lower() for topic in topics):
                    repo_fields.append("topics")

                if repo_fields:
                    fields.update(f"repo_{field}" for field in repo_fields)
                    repo_hits.append(
                        {
                            "name": repo.get("name"),
                            "url": repo.get("html_url"),
                            "matched_fields": repo_fields,
                        }
                    )

            if fields:
                matches.append(
                    {
                        "key": key,
                        "matched_fields": sorted(fields),
                        "repositories": repo_hits[:5],
                    }
                )

        return matches

    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
        url = f"{self.BASE_URL}{endpoint}"

        response = requests.get(
            url,
            headers=self.headers,
            params=params,
            timeout=self.timeout,
        )

        if response.status_code == 403:
            remaining = response.headers.get("X-RateLimit-Remaining")
            reset = response.headers.get("X-RateLimit-Reset")

            raise RuntimeError(
                f"GitHub API rate limit or access issue. "
                f"Remaining={remaining}, Reset={reset}"
            )

        response.raise_for_status()

        if self.sleep_between_requests > 0:
            time.sleep(self.sleep_between_requests)

        return response.json()
