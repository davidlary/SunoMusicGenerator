"""
Main CLI application for SunoMusicGenerator.

Provides commands for generating lyrics, songs, and cover art from scientific text.
"""

import click
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel

from ..core import get_logger, get_settings
from ..pipeline import LyricsGenerator, SongGenerator, CoverGenerator
from ..state import StateTracker

logger = get_logger(__name__)
console = Console()


@click.group()
@click.version_option(version="1.0.0", prog_name="suno-music-generator")
def cli():
    """
    SunoMusicGenerator - Transform scientific text into educational songs.

    Generate lyrics, audio, and cover art using Gemini and Suno APIs.
    """
    pass


@cli.command()
@click.argument("song_id")
@click.argument("narrative_file", type=click.Path(exists=True))
@click.option(
    "--prompt-template",
    type=click.Path(exists=True),
    default="prompts/EurekaProtocol.md",
    help="Path to lyrics generation prompt template"
)
@click.option(
    "--force",
    is_flag=True,
    help="Force regeneration even if lyrics exist"
)
def generate_lyrics(song_id: str, narrative_file: str, prompt_template: str, force: bool):
    """
    Generate lyrics from scientific narrative text.

    SONG_ID: Song identifier (e.g., 1.16.1)
    NARRATIVE_FILE: Path to text file with scientific content
    """
    try:
        console.print(f"\n[bold cyan]Generating Lyrics[/bold cyan]")
        console.print(f"Song ID: {song_id}")
        console.print(f"Narrative: {narrative_file}\n")

        # Read narrative
        narrative_path = Path(narrative_file)
        narrative_text = narrative_path.read_text()

        # Initialize generator
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Initializing...", total=None)

            generator = LyricsGenerator()

            progress.update(task, description="Generating lyrics via Gemini API...")
            result = generator.generate(
                song_id=song_id,
                narrative_text=narrative_text,
                prompt_template_path=Path(prompt_template),
                force_regenerate=force
            )

        # Display results
        if result["regenerated"]:
            console.print(f"\n[green]✓ Lyrics generated successfully[/green]")
        else:
            console.print(f"\n[yellow]→ Using existing lyrics[/yellow]")

        console.print(f"\nPath: {result['path']}")
        console.print(f"Model: {result['model']}")

        # Show preview
        lyrics = result['lyrics']
        preview = lyrics[:200] + "..." if len(lyrics) > 200 else lyrics
        console.print(f"\n[dim]{preview}[/dim]")

    except Exception as e:
        console.print(f"\n[red]✗ Error: {e}[/red]")
        logger.error(f"Lyrics generation failed: {e}", exc_info=True)
        raise click.Abort()


@cli.command()
@click.argument("song_id")
@click.argument("lyrics_file", type=click.Path(exists=True))
@click.option(
    "--title",
    required=True,
    help="Song title"
)
@click.option(
    "--tags",
    default="educational, rock",
    help="Genre/style tags for generation"
)
@click.option(
    "--formats",
    default="wav,mp3",
    help="Audio formats to download (comma-separated)"
)
@click.option(
    "--force",
    is_flag=True,
    help="Force regeneration even if audio exists"
)
def generate_audio(song_id: str, lyrics_file: str, title: str, tags: str, formats: str, force: bool):
    """
    Generate audio from lyrics using Suno API.

    SONG_ID: Song identifier (e.g., 1.16.1)
    LYRICS_FILE: Path to lyrics text file
    """
    try:
        console.print(f"\n[bold cyan]Generating Audio[/bold cyan]")
        console.print(f"Song ID: {song_id}")
        console.print(f"Title: {title}")
        console.print(f"Tags: {tags}\n")

        # Read lyrics
        lyrics_path = Path(lyrics_file)
        lyrics_text = lyrics_path.read_text()

        # Parse formats
        format_list = [f.strip() for f in formats.split(",")]

        # Initialize generator
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Initializing...", total=None)

            generator = SongGenerator()

            progress.update(task, description="Generating audio via Suno API...")
            result = generator.generate(
                song_id=song_id,
                lyrics=lyrics_text,
                title=title,
                tags=tags,
                download_formats=format_list,
                force_regenerate=force
            )

        # Display results
        if result["regenerated"]:
            console.print(f"\n[green]✓ Audio generated successfully[/green]")
        else:
            console.print(f"\n[yellow]→ Using existing audio[/yellow]")

        console.print(f"\nDirectory: {result['directory']}")
        console.print(f"Clips: {len(result['clip_ids'])}")

        # Show files
        if result.get("files"):
            console.print("\n[bold]Generated Files:[/bold]")
            for clip_id, files in result["files"].items():
                console.print(f"\n  {clip_id}:")
                for fmt, path in files.items():
                    console.print(f"    - {fmt}: {path}")

    except Exception as e:
        console.print(f"\n[red]✗ Error: {e}[/red]")
        logger.error(f"Audio generation failed: {e}", exc_info=True)
        raise click.Abort()


@cli.command()
@click.argument("song_id")
@click.argument("lyrics_file", type=click.Path(exists=True))
@click.option(
    "--prompt-template",
    type=click.Path(exists=True),
    default="prompts/CoverArtPrompt.md",
    help="Path to cover art generation prompt"
)
@click.option(
    "--force",
    is_flag=True,
    help="Force regeneration even if cover exists"
)
def generate_cover(song_id: str, lyrics_file: str, prompt_template: str, force: bool):
    """
    Generate cover art from lyrics using Gemini API.

    SONG_ID: Song identifier (e.g., 1.16.1)
    LYRICS_FILE: Path to lyrics text file
    """
    try:
        console.print(f"\n[bold cyan]Generating Cover Art[/bold cyan]")
        console.print(f"Song ID: {song_id}\n")

        # Read lyrics
        lyrics_path = Path(lyrics_file)
        lyrics_text = lyrics_path.read_text()

        # Initialize generator
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Initializing...", total=None)

            generator = CoverGenerator()

            progress.update(task, description="Generating cover art via Gemini API...")
            result = generator.generate(
                song_id=song_id,
                lyrics=lyrics_text,
                prompt_template_path=Path(prompt_template),
                force_regenerate=force
            )

        # Display results
        if result["regenerated"]:
            console.print(f"\n[green]✓ Cover art generated successfully[/green]")
        else:
            console.print(f"\n[yellow]→ Using existing cover art[/yellow]")

        console.print(f"\nPath: {result['path']}")
        console.print(f"Size: {result['size'] / 1024 / 1024:.2f} MB")

    except Exception as e:
        console.print(f"\n[red]✗ Error: {e}[/red]")
        logger.error(f"Cover generation failed: {e}", exc_info=True)
        raise click.Abort()


@cli.command()
@click.argument("song_id")
@click.argument("narrative_file", type=click.Path(exists=True))
@click.option(
    "--title",
    required=True,
    help="Song title"
)
@click.option(
    "--tags",
    default="educational, rock",
    help="Genre/style tags"
)
@click.option(
    "--lyrics-prompt",
    type=click.Path(exists=True),
    default="prompts/EurekaProtocol.md",
    help="Lyrics generation prompt"
)
@click.option(
    "--cover-prompt",
    type=click.Path(exists=True),
    default="prompts/CoverArtPrompt.md",
    help="Cover art generation prompt"
)
@click.option(
    "--force",
    is_flag=True,
    help="Force regeneration of all components"
)
def generate_all(
    song_id: str,
    narrative_file: str,
    title: str,
    tags: str,
    lyrics_prompt: str,
    cover_prompt: str,
    force: bool
):
    """
    Run full pipeline: lyrics -> audio -> cover art.

    SONG_ID: Song identifier (e.g., 1.16.1)
    NARRATIVE_FILE: Path to scientific narrative text
    """
    try:
        console.print(Panel.fit(
            f"[bold cyan]Full Generation Pipeline[/bold cyan]\n\n"
            f"Song ID: {song_id}\n"
            f"Title: {title}\n"
            f"Narrative: {narrative_file}",
            border_style="cyan"
        ))

        # Read narrative
        narrative_path = Path(narrative_file)
        narrative_text = narrative_path.read_text()

        # Step 1: Generate Lyrics
        console.print("\n[bold]Step 1/3: Generating Lyrics[/bold]")
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}")) as progress:
            progress.add_task("Generating lyrics...", total=None)
            lyrics_gen = LyricsGenerator()
            lyrics_result = lyrics_gen.generate(
                song_id=song_id,
                narrative_text=narrative_text,
                prompt_template_path=Path(lyrics_prompt),
                force_regenerate=force
            )
        console.print(f"[green]✓[/green] Lyrics: {lyrics_result['path']}")

        # Step 2: Generate Audio
        console.print("\n[bold]Step 2/3: Generating Audio[/bold]")
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}")) as progress:
            progress.add_task("Generating audio...", total=None)
            audio_gen = SongGenerator()
            audio_result = audio_gen.generate(
                song_id=song_id,
                lyrics=lyrics_result['lyrics'],
                title=title,
                tags=tags,
                download_formats=["wav", "mp3"],
                force_regenerate=force
            )
        console.print(f"[green]✓[/green] Audio: {audio_result['directory']}")

        # Step 3: Generate Cover Art
        console.print("\n[bold]Step 3/3: Generating Cover Art[/bold]")
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}")) as progress:
            progress.add_task("Generating cover art...", total=None)
            cover_gen = CoverGenerator()
            cover_result = cover_gen.generate(
                song_id=song_id,
                lyrics=lyrics_result['lyrics'],
                prompt_template_path=Path(cover_prompt),
                force_regenerate=force
            )
        console.print(f"[green]✓[/green] Cover: {cover_result['path']}")

        # Summary
        console.print(Panel.fit(
            f"[bold green]Generation Complete![/bold green]\n\n"
            f"Lyrics: {lyrics_result['path']}\n"
            f"Audio: {audio_result['directory']}\n"
            f"Cover: {cover_result['path']}",
            border_style="green"
        ))

    except Exception as e:
        console.print(f"\n[red]✗ Pipeline failed: {e}[/red]")
        logger.error(f"Full pipeline failed: {e}", exc_info=True)
        raise click.Abort()


@cli.command()
@click.argument("song_id", required=False)
def status(song_id: str = None):
    """
    Show generation status for songs.

    SONG_ID: Optional song ID to show specific status
    """
    try:
        tracker = StateTracker()

        if song_id:
            # Show specific song status
            state = tracker.state
            if song_id not in state["songs"]:
                console.print(f"[yellow]Song {song_id} not found[/yellow]")
                return

            song = state["songs"][song_id]

            console.print(Panel.fit(
                f"[bold cyan]Song Status: {song_id}[/bold cyan]",
                border_style="cyan"
            ))

            console.print(f"\n[bold]Source:[/bold] {song['source_path']}")
            console.print(f"[bold]Title:[/bold] {song['title']}")
            console.print(f"[bold]Created:[/bold] {song['created_at']}")

            # Lyrics
            if song.get("lyrics"):
                active = song["lyrics"]["active_version"]
                console.print(f"\n[bold]Lyrics:[/bold] {active}")

            # Audio
            if song.get("audio"):
                active = song["audio"]["active_version"]
                console.print(f"[bold]Audio:[/bold] {active}")

            # Cover
            if song.get("cover"):
                active = song["cover"]["active_version"]
                console.print(f"[bold]Cover:[/bold] {active}")

        else:
            # Show all songs
            state = tracker.state

            if not state["songs"]:
                console.print("[yellow]No songs generated yet[/yellow]")
                return

            table = Table(title="Generated Songs", show_header=True, header_style="bold cyan")
            table.add_column("Song ID", style="cyan")
            table.add_column("Title")
            table.add_column("Lyrics", justify="center")
            table.add_column("Audio", justify="center")
            table.add_column("Cover", justify="center")

            for song_id, song in state["songs"].items():
                has_lyrics = "✓" if song.get("lyrics") else "✗"
                has_audio = "✓" if song.get("audio") else "✗"
                has_cover = "✓" if song.get("cover") else "✗"

                table.add_row(
                    song_id,
                    song["title"][:40] + "..." if len(song["title"]) > 40 else song["title"],
                    has_lyrics,
                    has_audio,
                    has_cover
                )

            console.print(table)

    except Exception as e:
        console.print(f"\n[red]✗ Error: {e}[/red]")
        logger.error(f"Status check failed: {e}", exc_info=True)
        raise click.Abort()


if __name__ == "__main__":
    cli()
