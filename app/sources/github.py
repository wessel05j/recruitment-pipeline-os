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

    MIN_REPOS = 5
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
        results: List[Dict[str, Any]] = []
        checked_usernames: Set[str] = set()

        language_count = max(1, len(required_languages))
        per_language_quota = max(1, self.MAX_CANDIDATES // language_count)
        extra_slots = self.MAX_CANDIDATES - (per_language_quota * language_count)

        for index, language in enumerate(required_languages):
            language_quota = per_language_quota + (1 if index < extra_slots else 0)
            language_added = 0

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
                    if len(results) >= self.MAX_CANDIDATES:
                        return results

                    if language_added >= language_quota:
                        break

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
                        required_languages=required_languages,
                        signal_keys=signal_keys,
                    )

                    if candidate:
                        results.append(candidate)
                        language_added += 1
                        self.funnel_metrics["accepted_candidates"] += 1

                if language_added >= language_quota:
                    break

        return results

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
                f"repos:>{self.MIN_REPOS}",
                f"followers:>={self.MIN_FOLLOWERS}",
            ]
        )

        data = self._get(
            "/search/users",
            params={
                "q": query,
                "per_page": self.LIMIT_PER_PAGE,
                "page": page,
                "sort": "followers",
                "order": "desc",
            },
        )

        return data.get("items", [])

    def _process_candidate(
        self,
        username: str,
        required_languages: List[str],
        signal_keys: List[str],
    ) -> Optional[Dict[str, Any]]:
        self.funnel_metrics["users_considered"] += 1

        repos = self._fetch_user_repos(username)

        if not self._has_recent_repo_activity(repos):
            self.funnel_metrics["failed_recent_activity"] += 1
            return None

        self.funnel_metrics["passed_recent_activity"] += 1
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

        profile["matched_languages"] = sorted(language_counts.keys())
        profile["language_counts"] = language_counts
        profile["latest_repo_push"] = self._latest_repo_push(repos)
        profile["signal_keys"] = signal_keys
        profile["signal_matches"] = signal_matches
        profile["top_starred_repos"] = self._top_starred_repos(
            repos=repos,
            limit=self.TOP_STARRED_REPOS_LIMIT,
        )

        return profile

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
