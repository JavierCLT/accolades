from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from .models import CandidateItem
from .utils import normalize_url, trim_text


LOGGER = logging.getLogger(__name__)


class RedditSearchClient:
    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        self.client_id = client_id or os.getenv("REDDIT_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("REDDIT_CLIENT_SECRET")
        self.user_agent = user_agent or os.getenv("REDDIT_USER_AGENT")
        self._reddit = None

    @property
    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret and self.user_agent)

    def search(
        self,
        *,
        source_name: str,
        query_group: str,
        query: str,
        subreddits: list[str],
        result_limit: int = 20,
        sort: str = "new",
        time_filter: str = "day",
        is_forum_discussion: bool = True,
    ) -> list[CandidateItem]:
        if not self.is_configured:
            LOGGER.warning("Reddit API is not configured; skipping %s", source_name)
            return []

        reddit = self._client()
        results: list[CandidateItem] = []
        for subreddit_name in subreddits:
            try:
                subreddit = reddit.subreddit(subreddit_name)
                submissions = subreddit.search(
                    query=query,
                    sort=sort,
                    time_filter=time_filter,
                    limit=result_limit,
                )
                for submission in submissions:
                    candidate = self._to_candidate(
                        source_name=source_name,
                        query_group=query_group,
                        query=query,
                        subreddit_name=subreddit_name,
                        submission=submission,
                        is_forum_discussion=is_forum_discussion,
                    )
                    if candidate:
                        results.append(candidate)
            except Exception:
                LOGGER.exception(
                    "Reddit search failed for subreddit=%s query=%r",
                    subreddit_name,
                    query,
                )
        return results

    def _client(self):
        if self._reddit is not None:
            return self._reddit
        try:
            import praw
        except ImportError as exc:
            raise RuntimeError("praw is required for Reddit API access") from exc

        self._reddit = praw.Reddit(
            client_id=self.client_id,
            client_secret=self.client_secret,
            user_agent=self.user_agent,
            check_for_async=False,
        )
        return self._reddit

    def _to_candidate(
        self,
        *,
        source_name: str,
        query_group: str,
        query: str,
        subreddit_name: str,
        submission,
        is_forum_discussion: bool,
    ) -> CandidateItem | None:
        permalink = getattr(submission, "permalink", "")
        if not permalink:
            return None
        url = f"https://www.reddit.com{permalink}"
        title = trim_text(getattr(submission, "title", ""), 240)
        snippet_source = getattr(submission, "selftext", "") or getattr(submission, "url", "")
        snippet = trim_text(snippet_source, 500)
        created_utc = getattr(submission, "created_utc", None)
        published_date = None
        if created_utc:
            published_date = datetime.fromtimestamp(created_utc, timezone.utc).replace(microsecond=0).isoformat()
        return CandidateItem(
            source=f"{source_name}/r/{subreddit_name}",
            url=url,
            normalized_url=normalize_url(url),
            title=title,
            snippet=snippet,
            published_date=published_date,
            metadata={
                "source_kind": "reddit",
                "query_group": query_group,
                "query": query,
                "subreddit": subreddit_name,
                "score": getattr(submission, "score", None),
                "num_comments": getattr(submission, "num_comments", None),
                "is_forum_discussion": is_forum_discussion,
            },
        )
