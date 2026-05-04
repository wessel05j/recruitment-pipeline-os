import os
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

import requests
from dotenv import load_dotenv

load_dotenv()


class GitHubCandidateSearcher:
    BASE_URL = "https://api.github.com"

    MIN_REPOS = 5
    MIN_FOLLOWERS = 10
    RECENT_ACTIVITY_DAYS = 90
    LIMIT_PER_PAGE = 100
    MAX_SEARCH_PAGES_PER_LANGUAGE = 10  # GitHub max = 1000 search results
    MAX_CANDIDATES = 20
    REQUIRE_EMAIL = False
    REQUIRE_FULL_NAME = True

    def __init__(
        self,
        token: Optional[str] = None,
        timeout: int = 20,
        sleep_between_requests: float = 0.2,
    ):
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.timeout = timeout
        self.sleep_between_requests = sleep_between_requests

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
        bio_keys: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        self._validate_search_input(location, required_languages, bio_keys)

        bio_keys = bio_keys or []
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

                if not users:
                    break

                for user in users:
                    if len(results) >= self.MAX_CANDIDATES:
                        return results

                    if language_added >= language_quota:
                        break

                    username = user.get("login")

                    if not username:
                        continue

                    if username in checked_usernames:
                        continue

                    checked_usernames.add(username)

                    if user.get("type") != "User":
                        continue

                    candidate = self._process_candidate(
                        username=username,
                        required_languages=required_languages,
                        bio_keys=bio_keys,
                    )

                    if candidate:
                        results.append(candidate)
                        language_added += 1

                if language_added >= language_quota:
                    break

        return results

    def _validate_search_input(
        self,
        location: str,
        required_languages: List[str],
        bio_keys: Optional[List[str]],
    ) -> None:
        if not location or not isinstance(location, str):
            raise ValueError("location is required and must be a string.")

        if not required_languages or not isinstance(required_languages, list):
            raise ValueError("required_languages is required and must be a non-empty list.")

        if not all(isinstance(lang, str) and lang.strip() for lang in required_languages):
            raise ValueError("Each required language must be a non-empty string.")

        if bio_keys is not None:
            if not isinstance(bio_keys, list):
                raise ValueError("bio_keys must be a list if provided.")

            if not all(isinstance(key, str) and key.strip() for key in bio_keys):
                raise ValueError("Each bio key must be a non-empty string.")

    def _search_user_page(
        self,
        location: str,
        language: str,
        page: int,
    ) -> List[Dict[str, Any]]:
        query = (
            f"location:{location} "
            f"language:{language} "
            f"repos:>{self.MIN_REPOS} "
            f"followers:>{self.MIN_FOLLOWERS}"
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
        bio_keys: List[str],
    ) -> Optional[Dict[str, Any]]:
        repos = self._fetch_user_repos(username)

        if not self._has_recent_repo_activity(repos):
            return None

        language_counts = self._count_repo_languages(repos)

        if not self._has_all_required_languages(language_counts, required_languages):
            return None

        profile = self._fetch_user_profile(username)

        if not self._is_serious_candidate(profile, bio_keys):
            return None

        profile["matched_languages"] = sorted(language_counts.keys())
        profile["language_counts"] = language_counts
        profile["latest_repo_push"] = self._latest_repo_push(repos)

        return profile

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

    def _is_serious_candidate(
        self,
        profile: Dict[str, Any],
        bio_keys: List[str],
    ) -> bool:
        if self.REQUIRE_FULL_NAME and not self._has_full_name(profile.get("name")):
            return False

        if self.REQUIRE_EMAIL and not profile.get("email"):
            return False

        if bio_keys and not self._bio_contains_key(profile.get("bio"), bio_keys):
            return False

        return True

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

    def _bio_contains_key(self, bio: Optional[str], bio_keys: List[str]) -> bool:
        if not bio:
            return False

        bio_lower = bio.lower()
        return any(key.lower() in bio_lower for key in bio_keys)

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