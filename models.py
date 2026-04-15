from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


# ---------- Internal data models ----------


class IGComment(BaseModel):
    """A single Instagram comment."""

    author: str
    text: str
    likes_count: int
    comment_id: str


class IGPost(BaseModel):
    """Fetched Instagram post with its comments."""

    url: str
    shortcode: str
    caption: str
    author: str
    like_count: int
    comment_count: int
    comments: list[IGComment]


class RedditComment(BaseModel):
    """A single Reddit comment or reply."""

    author: str
    text: str
    score: int
    comment_id: str


class RedditPost(BaseModel):
    """Fetched Reddit post with its comments."""

    url: str
    post_id: str
    title: str
    selftext: str
    author: str
    score: int
    num_comments: int
    subreddit: str
    comments: list[RedditComment]


# ---------- Gemini response schema ----------


class Sentiment(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


SENTIMENT_COLORS = {
    Sentiment.POSITIVE: "green",
    Sentiment.NEGATIVE: "red",
    Sentiment.NEUTRAL: "yellow",
}


class Theme(BaseModel):
    """A recurring theme or topic found in the comments."""

    title: str = Field(description="Short label for the theme (e.g. 'Outfit praise')")
    description: str = Field(description="One sentence describing what people say about this theme")


class Camp(BaseModel):
    """A distinct viewpoint or side identified in the discussion."""

    label: str = Field(description="Short name for this position (e.g. 'Pro-patch', 'Anti-patch')")
    description: str = Field(description="One sentence summarising what people in this camp believe")


class CommenterSentiment(BaseModel):
    """Sentiment and optional stance classification for a single commenter."""

    author: str = Field(description="Username of the commenter")
    sentiment: Sentiment = Field(description="Overall emotional tone of this commenter")
    stance: str | None = Field(
        default=None,
        description="Which camp this commenter aligns with (must exactly match a camp label), or null if no camps were identified or this commenter does not clearly align with any"
    )
    reason: str = Field(description="Brief one-sentence reason for the sentiment and stance classification")


class AnalysisResult(BaseModel):
    """Complete analysis of a post's comments."""

    summary: str = Field(
        description="A 3-5 sentence overview of what people are saying in the comments"
    )
    themes: list[Theme] = Field(
        description="2-5 recurring themes or topics found across the comments"
    )
    camps: list[Camp] = Field(
        default_factory=list,
        description="0-3 distinct viewpoints or sides if the discussion has a clear debate or split opinion. Leave empty if there is no meaningful divide."
    )
    commenter_sentiments: list[CommenterSentiment] = Field(
        description="Sentiment classification for every commenter provided. Do not skip any."
    )
