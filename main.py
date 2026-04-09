import argparse
import sys
from pathlib import Path

EXPORTS_DIR = Path(__file__).parent / "exports"

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from models import AnalysisResult, IGPost, Sentiment, SENTIMENT_COLORS
from ig_client import fetch_post
from summariser import analyse_post

console: Console


def display_results(post: IGPost, analysis: AnalysisResult) -> None:
    console.print()
    _display_header(post)
    _display_summary(analysis.summary)
    _display_themes(analysis.themes)
    _display_sentiment(analysis.commenter_sentiments)
    console.print()


def _display_header(post: IGPost) -> None:
    subtitle = f"@{post.author}  |  {post.like_count:,} likes  |  {post.comment_count:,} comments"

    caption_preview = post.caption[:200].replace("\n", " ") if post.caption else "(no caption)"
    if len(post.caption or "") > 200:
        caption_preview += "…"

    console.print(Panel(caption_preview, title="Instagram Post", subtitle=subtitle, border_style="cyan"))


def _display_summary(summary: str) -> None:
    console.print(Panel(summary, title="Comment Summary", border_style="green"))


def _display_themes(themes: list) -> None:
    if not themes:
        return

    table = Table(title="Recurring Themes", show_lines=True, border_style="magenta")
    table.add_column("Theme", style="bold", min_width=20)
    table.add_column("What people say", ratio=2)

    for t in themes:
        table.add_row(t.title, t.description)

    console.print(table)


def _display_sentiment(sentiments: list) -> None:
    total = len(sentiments)
    if total == 0:
        console.print("[dim]No commenter sentiments to display.[/dim]")
        return

    positive = sum(1 for s in sentiments if s.sentiment == Sentiment.POSITIVE)
    negative = sum(1 for s in sentiments if s.sentiment == Sentiment.NEGATIVE)
    neutral = sum(1 for s in sentiments if s.sentiment == Sentiment.NEUTRAL)

    console.print()
    console.print("[bold]Sentiment Breakdown[/bold]")
    console.print()

    bar_width = 30
    _print_bar("Positive", positive, total, bar_width, SENTIMENT_COLORS[Sentiment.POSITIVE])
    _print_bar("Negative", negative, total, bar_width, SENTIMENT_COLORS[Sentiment.NEGATIVE])
    _print_bar("Neutral", neutral, total, bar_width, SENTIMENT_COLORS[Sentiment.NEUTRAL])

    console.print()

    table = Table(title="Per-Commenter Sentiment", show_lines=True)
    table.add_column("Author", style="bold")
    table.add_column("Sentiment")
    table.add_column("Reason", ratio=2)

    sentiment_order = {Sentiment.POSITIVE: 0, Sentiment.NEGATIVE: 1, Sentiment.NEUTRAL: 2}
    sorted_sentiments = sorted(sentiments, key=lambda s: sentiment_order[s.sentiment])

    for s in sorted_sentiments:
        colour = SENTIMENT_COLORS[s.sentiment]
        table.add_row(
            f"@{s.author}",
            Text(s.sentiment.value.upper(), style=f"bold {colour}"),
            s.reason,
        )

    console.print(table)


def _print_bar(label: str, count: int, total: int, width: int, colour: str) -> None:
    pct = (count / total * 100) if total > 0 else 0
    filled = int(width * count / total) if total > 0 else 0
    bar = "\u2588" * filled + "\u2591" * (width - filled)
    console.print(
        f"  [{colour}]{label:>8}[/]: {count:>3} ({pct:>5.1f}%)  [{colour}]{bar}[/]"
    )


def main() -> None:
    global console

    parser = argparse.ArgumentParser(description="Summarise an Instagram post's comments.")
    parser.add_argument("url", help="Instagram post URL")
    parser.add_argument("--export", action="store_true", help="Export results to an SVG file")
    args = parser.parse_args()

    console = Console(record=args.export)

    try:
        with console.status("[bold green]Logging in and fetching Instagram post..."):
            post = fetch_post(args.url)
        console.print(
            f"[green]Fetched {len(post.comments)} comments from @{post.author}[/green]"
        )

        with console.status("[bold green]Analysing with Gemini..."):
            analysis = analyse_post(post)

        display_results(post, analysis)

        if args.export:
            EXPORTS_DIR.mkdir(exist_ok=True)
            filepath = EXPORTS_DIR / f"ig_{post.shortcode}.svg"
            filepath.write_text(console.export_svg(title=f"@{post.author}"), encoding="utf-8")
            console.print(f"[dim]Exported to {filepath}[/dim]")

    except ValueError as e:
        console.print(f"[bold red]Invalid URL or post not found:[/] {e}")
        sys.exit(1)
    except PermissionError as e:
        console.print(f"[bold red]Access denied:[/] {e}")
        sys.exit(1)
    except ConnectionError as e:
        console.print(f"[bold red]Connection error:[/] {e}")
        sys.exit(1)
    except RuntimeError as e:
        console.print(f"[bold red]Analysis failed:[/] {e}")
        console.print("[dim]Check your GEMINI_API_KEY and API quota.[/dim]")
        sys.exit(1)


if __name__ == "__main__":
    main()
