"""
SerienStream Downloader - Entry point.

Two modes:
  1. No arguments  ->  interactive menu
  2. With URL       ->  direct download (CLI mode)
"""

import sys


def cli_mode(target_url: str):
    """Classic mode: URL passed as argument."""
    import pipeline
    from scraper import CatalogScraper
    from settings import load_settings

    settings = load_settings()

    with CatalogScraper() as scraper:
        print(f"[*] Starting analysis for: {target_url}")
        print(f"[*] Active domain: {scraper.get_active_domain()}")

        series_title, episodes, kind = pipeline.resolve_episodes(scraper, target_url)
        print(f"[+] Series title: {series_title}")

        if kind == "series":
            episodes = pipeline.ask_seasons(scraper, target_url)

        if not episodes:
            print("[!] No episodes found.")
            sys.exit(1)

        print(f"\n[*] {len(episodes)} episodes to download.")

        available = pipeline.collect_providers(scraper, episodes[0]["url"])
        preferred = pipeline.fix_provider(settings.get("preferred_provider", "VOE"))

        print(f"\nAvailable providers: {', '.join(available) if available else 'none detected'}")
        chosen = input(f">>> Which provider? (default: {preferred}): ").strip() or preferred
        chosen = pipeline.fix_provider(chosen)

        if available and chosen not in available:
            print(f"[!] '{chosen}' not available, using {available[0]}.")
            chosen = available[0]

        print(f"[+] Selected provider: {chosen}")

        from pathlib import Path
        download_dir = Path(settings["download_path"]) / pipeline.sanitize_filename(series_title)
        print(f"[+] Target folder: {download_dir}\n")

        pipeline.run_download(
            episodes=episodes,
            provider=chosen,
            series_title=series_title,
            download_dir=str(download_dir),
        )


def main():
    """Main entry point - starts menu or CLI mode."""
    if len(sys.argv) >= 2:
        cli_mode(sys.argv[1])
        return

    try:
        import menu
    except ImportError as e:
        print(f"[!] Menu not available ({e}).")
        print("[!] Install dependencies:")
        print("    pip install questionary rich")
        sys.exit(1)

    try:
        menu.run()
    except KeyboardInterrupt:
        print("\n[*] Exited.")


if __name__ == "__main__":
    main()
