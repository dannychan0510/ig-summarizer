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


class CommenterSentiment(BaseModel):
    """Sentiment classification for a single commenter."""

    author: str = Field(description="Instagram username of the commenter")
    sentiment: Sentiment = Field(description="Overall sentiment of this commenter")
    reason: str = Field(description="Brief one-sentence reason for the classification")


class AnalysisResult(BaseModel):
    """Complete analysis of an Instagram post's comments."""

    summary: str = Field(
        description="A 3-5 sentence overview of what people are saying in the comments"
    )
    themes: list[Theme] = Field(
        description="2-5 recurring themes or topics found across the comments"
    )
    commenter_sentiments: list[CommenterSentiment] = Field(
        description="Sentiment classification for every commenter provided. Do not skip any."
    )
