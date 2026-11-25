"""Interactive main menu with all features."""

from pathlib import Path

import questionary
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

import pipeline
import search
from scraper import CatalogScraper
from settings import (
    ASPECT_CHECK,
    ASPECT_MODES,
    CONFIG_FILE,
    PROVIDERS,
    QUALITIES,
    VERSION,
    load_settings,
    save_settings,
)


console = Console()

TURQUOISE = "#40E0D0"

BANNER = "\n".join([
    "███████╗████████╗██████╗ ███████╗ █████╗ ███╗   ███╗██████╗  ██████╗ ██╗  ██╗",
    "██╔════╝╚══██╔══╝██╔══██╗██╔════╝██╔══██╗████╗ ████║██╔══██╗██╔═══██╗╚██╗██╔╝",
    "███████╗   ██║   ██████╔╝█████╗  ███████║██╔████╔██║██████╔╝██║   ██║ ╚███╔╝ ",
    "╚════██║   ██║   ██╔══██╗██╔══╝  ██╔══██║██║╚██╔╝██║██╔══██╗██║   ██║ ██╔██╗ ",
    "███████║   ██║   ██║  ██║███████╗██║  ██║██║ ╚═╝ ██║██████╔╝╚██████╔╝██╔╝ ██╗",
    "╚══════╝   ╚═╝   ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝╚═════╝  ╚═════╝ ╚═╝  ╚═╝",
])


def show_banner(effects: bool):
    """Shows the startup banner."""
    console.print()
    style = f"bold {TURQUOISE}" if effects else TURQUOISE
    console.print(Text(BANNER, style=style), justify="center")

    welcome_panel = Panel(
        f"[bold {TURQUOISE}]Welcome to StreamBox![/]  [dim]v{VERSION}[/dim]\n"
        f"[{TURQUOISE}]Download episodes, seasons, or entire series.[/]",
        border_style=TURQUOISE,
        expand=False,
    )
    console.print(Align.center(welcome_panel))
    console.print()


def spinner(label: str, effects: bool):
    """Returns a spinner or a plain print."""
    if effects:
        return console.status(f"[{TURQUOISE}]{label}[/]", spinner="dots")

    class _Plain:
        def __enter__(self):
            print(f"[*] {label}")
            return self

        def __exit__(self, *a):
            return False

    return _Plain()


# ---------------------------------------------------------------- Search

def search_flow(settings: dict):
    """Search for a series and start download."""
    effects = settings.get("menu_effects", False)

    query = questionary.text("Enter movie or series name:").ask()
    if not query or not query.strip():
        console.print("[yellow]No input, returning to menu.[/yellow]")
        return

    results = []
    with spinner(f"Searching for '{query}'...", effects):
        try:
            raw = search.search_series(query, debug=False)
            results = search.fuzzy_match(query, raw)
        except Exception as e:
            console.print(f"[red]Search failed: {e}[/red]")

    if not results:
        console.print()
        console.print(
            Panel(
                "[yellow]No results found.[/yellow]\n\n"
                "Possible reasons:\n"
                "  - Check spelling\n"
                "  - The series cache may be outdated\n\n"
                "[bold]Tip:[/bold] Use 'Refresh Cache' in the main menu.",
                title="Search",
                border_style="yellow",
            )
        )

        use_url = questionary.confirm(
            "Paste a URL directly instead?", default=True
        ).ask()

        if use_url:
            url_flow(settings)
        return

    shown = results[:30]
    labels = [r['title'] for r in shown]

    console.print()
    console.print(f"[green]{len(results)} results found[/green]\n")

    picked = questionary.select(
        "Select a result:",
        choices=labels + ["Cancel"],
    ).ask()

    if not picked or picked == "Cancel":
        return

    idx = labels.index(picked)
    target = shown[idx]["url"]
    console.print(f"\n[{TURQUOISE}]Selected:[/] {target}\n")

    start_download(settings, target)


def url_flow(settings: dict):
    """Download via a directly pasted URL."""
    url = questionary.text(
        "Paste SerienStream URL (series, season, or episode):"
    ).ask()

    if not url or not url.strip():
        return

    start_download(settings, url.strip())


# ------------------------------------------------------------- Download

def start_download(settings: dict, target_url: str):
    """Runs the complete download flow for a URL."""
    effects = settings.get("menu_effects", False)

    with CatalogScraper() as scraper:
        with spinner("Analyzing URL...", effects):
            try:
                series_title, episodes, kind = pipeline.resolve_episodes(scraper, target_url)
            except Exception as e:
                console.print(f"[red]Error analyzing URL: {e}[/red]")
                return

        console.print(f"[green]Series title:[/green] {series_title}")

        if kind == "series":
            episodes = pipeline.ask_seasons(scraper, target_url)
            if not episodes:
                return

        if not episodes:
            console.print("[red]No episodes found.[/red]")
            return

        console.print(f"\n[green]{len(episodes)} episodes[/green] available.")
        console.print(
            "[dim]💡 TIP: Press SPACE to select, then ENTER to confirm![/dim]"
        )
        console.print("[dim]   CTRL+A = Select all | CTRL+R = Deselect all[/dim]\n")

        choices = []
        for ep in episodes:
            season = ep.get("season", 1)
            number = ep.get("number", 0)
            label = f"{series_title} - Season {season} - Episode {number}"
            choices.append({"name": label, "value": ep, "checked": False})

        selected = questionary.checkbox(
            "Select episodes (SPACE = Select, ENTER = Confirm, CTRL+A = Select All):",
            choices=choices,
        ).ask()

        if not selected:
            console.print("[yellow]No episodes selected, returning to menu.[/yellow]")
            return

        console.print(f"\n[green]{len(selected)} episodes selected.[/green]\n")

        # Provider
        preferred = pipeline.fix_provider(settings.get("preferred_provider", "VOE"))
        available = []
        try:
            available = pipeline.collect_providers(scraper, selected[0]["url"])
        except Exception:
            pass

    provider_choices = list(dict.fromkeys(available + PROVIDERS))
    provider = questionary.select(
        "Which provider?",
        choices=provider_choices,
        default=preferred if preferred in provider_choices else provider_choices[0],
    ).ask()

    if not provider:
        return

    # Quality
    preferred_quality = settings.get("preferred_quality", "1080p")
    quality = questionary.select(
        "Which quality?",
        choices=QUALITIES,
        default=preferred_quality if preferred_quality in QUALITIES else QUALITIES[0],
    ).ask()

    if not quality:
        return

    # Aspect ratio
    aspect_mode = settings.get("aspect_correction", ASPECT_CHECK)
    console.print(f"[dim]Aspect ratio: {aspect_mode}[/dim]")

    download_dir = Path(settings.get("download_path")) / pipeline.sanitize_filename(series_title)
    console.print(f"[dim]Target folder: {download_dir}[/dim]\n")

    if not questionary.confirm("Start download now?", default=True).ask():
        return

    console.print(
        Panel(
            f"[bold {TURQUOISE}]Important Notes[/bold {TURQUOISE}]\n\n"
            "1. A browser window will open automatically.\n"
            "2. Solve the captcha manually for the [bold]first[/bold] episode (max 50 seconds).\n"
            "3. After that, all remaining episodes will run automatically.\n"
            "4. Do not close the terminal until the download is finished.\n"
            "5. Already existing files will be skipped.\n"
            "6. Audio and video are copied 1:1, the format is preserved.",
            border_style=TURQUOISE,
        )
    )
    input("\n>>> Press ENTER to start...")

    success, failed, skipped = pipeline.run_download(
        episodes=selected,
        provider=pipeline.fix_provider(provider),
        series_title=series_title,
        download_dir=str(download_dir),
        preferred_quality=quality,
        resume=settings.get("resume_downloads", True),
        skip_existing=settings.get("skip_existing", True),
        notify=settings.get("notifications", True),
        aspect_mode=aspect_mode,
    )

    summary_table = Table(show_header=False, box=None, padding=(0, 2))
    summary_table.add_column("Status", style="bold")
    summary_table.add_column("Count", justify="right")
    summary_table.add_row("[green]✓ Newly downloaded[/green]", str(success))
    summary_table.add_row("[blue]● Already existed[/blue]", str(skipped))
    summary_table.add_row("[red]✗ Failed[/red]", str(failed))
    summary_table.add_row("[dim]Folder[/dim]", f"[dim]{download_dir}[/dim]")

    console.print(
        Panel(
            summary_table,
            title="[bold green]Download Summary[/bold green]",
            border_style="green",
            expand=False,
        )
    )

    input("\n>>> Press ENTER to return to menu...")


# ------------------------------------------------------------- Settings

def settings_flow(settings: dict):
    """Settings menu."""
    while True:
        console.print()
        choice = questionary.select(
            "Settings:",
            choices=[
                f"📁 Download Path [{settings['download_path']}]",
                f"🎬 Preferred Provider [{settings['preferred_provider']}]",
                f"🎯 Preferred Quality [{settings['preferred_quality']}]",
                f"🖥️  Aspect Ratio [{settings['aspect_correction']}]",
                f"🔄 Resume Downloads [{'ON' if settings['resume_downloads'] else 'OFF'}]",
                f"⏭️  Skip Existing Files [{'ON' if settings['skip_existing'] else 'OFF'}]",
                f"🔔 Desktop Notifications [{'ON' if settings['notifications'] else 'OFF'}]",
                f"✨ Menu Effects [{'ON' if settings['menu_effects'] else 'OFF'}]",
                "↩️  Back",
            ],
        ).ask()

        if not choice or choice.startswith("↩"):
            save_settings(settings)
            return

        if choice.startswith("📁"):
            new = questionary.text(
                "New download path:", default=settings["download_path"]
            ).ask()
            if new:
                settings["download_path"] = new
                Path(new).mkdir(parents=True, exist_ok=True)
                console.print(f"[green]Saved:[/green] {new}")

        elif choice.startswith("🎬"):
            new = questionary.select("Choose provider:", choices=PROVIDERS).ask()
            if new:
                settings["preferred_provider"] = pipeline.fix_provider(new)
                console.print(f"[green]Saved:[/green] {settings['preferred_provider']}")

        elif choice.startswith("🎯"):
            new = questionary.select("Choose quality:", choices=QUALITIES).ask()
            if new:
                settings["preferred_quality"] = new
                console.print(f"[green]Saved:[/green] {new}")

        elif choice.startswith("🖥"):
            console.print(
                Panel(
                    "[bold]Off (keep original)[/bold]\n"
                    "  File stays exactly as from the source.\n\n"
                    "[bold]Check and report[/bold]  (recommended)\n"
                    "  Shows resolution, SAR, and actual display ratio.\n"
                    "  Warns about unusual values.\n\n"
                    "[bold]Set SAR to 1:1[/bold]\n"
                    "  Metadata only. For players that otherwise stretch the image.\n\n"
                    "[bold]Force 16:9[/bold]\n"
                    "  Metadata only. For widescreen series that appear squished.\n\n"
                    "[dim]All corrections without re-encoding, no quality loss.[/dim]",
                    title="Explanation",
                    border_style=TURQUOISE,
                )
            )
            new = questionary.select("Choose mode:", choices=ASPECT_MODES).ask()
            if new:
                settings["aspect_correction"] = new
                console.print(f"[green]Saved:[/green] {new}")

        elif choice.startswith("🔄"):
            settings["resume_downloads"] = not settings["resume_downloads"]
            console.print(
                f"[green]Resume Downloads:[/green] "
                f"{'ON' if settings['resume_downloads'] else 'OFF'}"
            )

        elif choice.startswith("⏭"):
            settings["skip_existing"] = not settings["skip_existing"]
            console.print(
                f"[green]Skip Existing Files:[/green] "
                f"{'ON' if settings['skip_existing'] else 'OFF'}"
            )

        elif choice.startswith("🔔"):
            settings["notifications"] = not settings["notifications"]
            console.print(
                f"[green]Desktop Notifications:[/green] "
                f"{'ON' if settings['notifications'] else 'OFF'}"
            )

        elif choice.startswith("✨"):
            settings["menu_effects"] = not settings["menu_effects"]
            console.print(
                f"[green]Menu Effects:[/green] "
                f"{'ON' if settings['menu_effects'] else 'OFF'}"
            )

        save_settings(settings)


# --------------------------------------------------- Uninstall Help

def uninstall_help():
    """Shows the complete uninstall guide."""
    app_dir = Path(__file__).resolve().parent
    console.print()
    console.print(
        Panel(
            f"[bold {TURQUOISE}]=== UNINSTALL GUIDE ===[/bold {TURQUOISE}]\n\n"
            "[bold]1. Uninstall Python packages:[/bold]\n"
            "   [green]pip uninstall questionary rich patchright httpx selectolax yt-dlp plyer[/green]\n\n"
            "[bold]2. Delete program folder and venv:[/bold]\n"
            f"   [green]rmdir /s {app_dir}[/green]\n\n"
            "[bold]3. Remove external system programs:[/bold]\n"
            "   [dim]Windows (Winget):[/dim] [green]winget uninstall ffmpeg yt-dlp[/green]\n"
            "   [dim]macOS (Homebrew):[/dim] [green]brew uninstall ffmpeg yt-dlp[/green]\n"
            "   [dim]Linux (Apt):[/dim]      [green]sudo apt remove ffmpeg yt-dlp[/green]\n\n"
            "[bold]4. Delete saved settings and cache:[/bold]\n"
            f"   [yellow]{CONFIG_FILE.parent}[/yellow]\n\n"
            "[dim]After that, everything is completely removed from your PC.[/dim]",
            border_style="red",
            title="Uninstall",
        )
    )
    input("\n>>> Press ENTER to go back to the menu...")


# --------------------------------------------------- Cache

def cache_refresh_flow(effects: bool = False):
    """Refreshes the series cache."""
    console.print()
    if questionary.confirm("Refresh cache now?", default=True).ask():
        with spinner("Refreshing cache...", effects):
            success = search.refresh_cache(debug=False)

        if success:
            console.print("[green]✓ Cache refreshed successfully![/green]")
        else:
            console.print("[red]✗ Cache refresh failed![/red]")

    input("\n>>> Press ENTER to return to menu...")


# ------------------------------------------------------------- Main Menu

def run():
    """Entry point of the interactive menu."""
    settings = load_settings()
    Path(settings["download_path"]).mkdir(parents=True, exist_ok=True)

    while True:
        effects = settings.get("menu_effects", False)
        show_banner(effects)

        choice = questionary.select(
            "What would you like to do?",
            choices=[
                "🔍 Search Movie/Series",
                "🔗 Paste URL",
                "⚙️  Settings",
                "🔄 Refresh Cache",
                "🗑️  Uninstall Help",
                "👋 Exit",
            ],
        ).ask()

        if choice is None or choice.startswith("👋"):
            save_settings(settings)
            console.print("\n[dim]See you next time![/dim]\n")
            break

        if choice.startswith("🔍"):
            search_flow(settings)
        elif choice.startswith("🔗"):
            url_flow(settings)
        elif choice.startswith("⚙"):
            settings_flow(settings)
        elif choice.startswith("🔄"):
            cache_refresh_flow(effects)
        elif choice.startswith("🗑"):
            uninstall_help()

        save_settings(settings)
