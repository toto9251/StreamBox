"""Download pipeline with progress, resume, login check, and referer handling."""

import json
import os
import queue
import re
import subprocess
import threading
import time
from math import gcd
from pathlib import Path

from patchright.sync_api import sync_playwright
from plyer import notification

from config import Config
from settings import ASPECT_OFF, ASPECT_CHECK, ASPECT_SAR1, ASPECT_169


PROVIDER_FIXES = {
    "VEO": "VOE", "VOE": "VOE",
    "DOOD": "Doodstream", "DOODSTREAM": "Doodstream",
    "STREAMTAPE": "Streamtape", "TAPE": "Streamtape",
    "VIDOZA": "Vidoza",
}

IGNORED_HOSTS = ("jwpltx.com", "ping.gif")

# VOE CDN requires these headers, otherwise the download hangs
VOE_REFERER = "https://voe.sx/"

# Abort if no progress for 30 seconds
STALL_TIMEOUT = 30

KNOWN_RATIOS = [
    ("1:1", 1.0),
    ("4:3", 4 / 3),
    ("16:10", 16 / 10),
    ("16:9", 16 / 9),
    ("1.85:1", 1.85),
    ("2:1", 2.0),
    ("2.39:1", 2.39),
]

RATIO_TOLERANCE = 0.12


# --------------------------------------------------------------- Helpers

def fix_provider(name: str) -> str:
    return PROVIDER_FIXES.get((name or "").strip().upper(), (name or "").strip())


def sanitize_filename(name: str) -> str:
    for c in '<>:"/\\|?*':
        name = name.replace(c, "")
    name = name.replace(" ", "_")
    name = re.sub(r"_+", "_", name)
    return name.strip("._")


def format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def format_time(seconds: int) -> str:
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours}h {minutes:02d}m {secs:02d}s"
    elif minutes > 0:
        return f"{minutes}m {secs:02d}s"
    else:
        return f"{secs}s"


def send_notification(title: str, message: str):
    try:
        notification.notify(
            title=title,
            message=message,
            app_name="StreamBox",
            timeout=10,
        )
    except Exception:
        pass


def pick_best_url(urls: list, preferred_quality: str = "1080p") -> str:
    if not urls:
        return None
    if len(urls) == 1:
        return urls[0]

    quality_urls = {}
    for url in urls:
        match = re.search(r'(\d{3,4})p', url)
        if match:
            quality_urls[match.group(1) + "p"] = url

    if preferred_quality in quality_urls:
        return quality_urls[preferred_quality]

    for q in ("1080p", "720p", "480p"):
        if q in quality_urls:
            return quality_urls[q]

    for key in ("master.m3u8", ".m3u8", ".mp4"):
        hits = [u for u in urls if key in u]
        if hits:
            return hits[0]

    return urls[0]


def build_browser_context(p, user_data_dir: str):
    kwargs = dict(
        user_data_dir=user_data_dir,
        headless=False,
        args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        ignore_default_args=["--enable-automation"],
        user_agent=Config.USER_AGENT,
    )
    try:
        return p.chromium.launch_persistent_context(channel="chrome", **kwargs)
    except Exception:
        return p.chromium.launch_persistent_context(**kwargs)


# ---------------------------------------------------------- Login Check

def check_login_status(browser_context) -> bool:
    """Checks if the user is still logged in."""
    page = browser_context.new_page()
    try:
        page.goto("https://serienstream.to/", wait_until="load", timeout=15000)
        page.wait_for_timeout(2000)

        content = page.content().lower()

        if "/logout" in content:
            print("[+] Login status: Logged in")
            page.close()
            return True

        login_form = page.locator('form[action*="login"], input[name="password"]')
        if login_form.count() > 0:
            print("[-] Login status: NOT logged in!")
            print("[!] Please run 'python manual_auth.py' to log in.")
            page.close()
            return False

        print("[?] Login status: Unclear, trying anyway...")
        page.close()
        return True

    except Exception as e:
        print(f"[!] Login check failed: {e}")
        try:
            page.close()
        except Exception:
            pass
        return False


# --------------------------------------------------- Aspect Ratio

def probe_video(filepath) -> dict:
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,width,height,sample_aspect_ratio,display_aspect_ratio",
        "-show_entries", "format=duration,size",
        "-of", "json", str(filepath),
    ]
    try:
        out = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=90,
        )
        if out.returncode != 0:
            return {}
        data = json.loads(out.stdout or "{}")
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        return {}

    info = {}
    streams = data.get("streams") or []
    if streams:
        s = streams[0]
        info["codec"] = str(s.get("codec_name") or "unknown")
        info["width"] = int(s.get("width") or 0)
        info["height"] = int(s.get("height") or 0)
        info["sar"] = str(s.get("sample_aspect_ratio") or "1:1")
        info["dar"] = str(s.get("display_aspect_ratio") or "")

    fmt = data.get("format") or {}
    try:
        info["duration"] = float(fmt.get("duration") or 0)
    except (ValueError, TypeError):
        info["duration"] = 0.0
    try:
        info["size"] = int(fmt.get("size") or 0)
    except (ValueError, TypeError):
        info["size"] = 0

    return info


def parse_ratio(value: str):
    if not value or ":" not in value:
        return None
    try:
        num, den = value.split(":", 1)
        num, den = int(num.strip()), int(den.strip())
    except (ValueError, TypeError):
        return None
    if num <= 0 or den <= 0:
        return None
    return num, den


def display_ratio(info: dict):
    w = info.get("width", 0)
    h = info.get("height", 0)
    if not w or not h:
        return None
    sar = parse_ratio(info.get("sar", "1:1")) or (1, 1)
    return (w * sar[0] / sar[1]) / h


def nearest_ratio(value: float):
    name, target = min(KNOWN_RATIOS, key=lambda kv: abs(kv[1] - value))
    return name, abs(target - value)


def fix_aspect(filepath, mode: str) -> bool:
    if mode in (ASPECT_OFF, ASPECT_CHECK):
        return False

    info = probe_video(filepath)
    if not info:
        print("[!] ffprobe could not read the file, no correction applied.")
        return False

    codec = info.get("codec", "")
    if codec in ("h264", "avc1"):
        bsf_name = "h264_metadata"
    elif codec in ("hevc", "h265", "hev1", "hvc1"):
        bsf_name = "hevc_metadata"
    else:
        print(f"[!] Codec '{codec}' does not support metadata correction.")
        return False

    w, h = info.get("width", 0), info.get("height", 0)
    if not w or not h:
        return False

    if mode == ASPECT_SAR1:
        sar = parse_ratio(info.get("sar", "1:1")) or (1, 1)
        if sar == (1, 1):
            print("[=] SAR is already 1:1, nothing to do.")
            return False
        sar_spec = "1/1"

    elif mode == ASPECT_169:
        num = 16 * h
        den = 9 * w
        g = gcd(num, den)
        sar_spec = f"{num // g}/{den // g}"
        if sar_spec == "1/1":
            print("[=] Video is already 16:9, nothing to do.")
            return False

    else:
        return False

    tmp = filepath.with_suffix(".tmp_aspect.mp4")
    cmd = [
        "ffmpeg", "-y", "-i", str(filepath),
        "-c", "copy",
        "-bsf:v", f"{bsf_name}=sample_aspect_ratio={sar_spec}",
        "-movflags", "+faststart",
        str(tmp),
    ]

    print(f"[*] Correcting aspect ratio (SAR={sar_spec}, metadata only)...")
    result = subprocess.run(cmd, capture_output=True)

    if result.returncode != 0 or not tmp.exists() or tmp.stat().st_size == 0:
        print("[-] Correction failed, original file unchanged.")
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        return False

    try:
        os.replace(str(tmp), str(filepath))
    except OSError as e:
        print(f"[-] Could not replace file: {e}")
        return False

    print(f"[+] Aspect ratio corrected: {filepath.name}")
    return True


def verify_episode(filepath, mode: str):
    info = probe_video(filepath)
    if not info:
        print("[!] Format check not possible. Is ffprobe installed?")
        return

    w = info.get("width", 0)
    h = info.get("height", 0)
    sar = info.get("sar", "1:1")
    ratio = display_ratio(info)

    line = f"[*] Format: {w}x{h} | SAR {sar}"
    if ratio:
        name, diff = nearest_ratio(ratio)
        line += f" | Display {ratio:.3f} (~{name})"
    print(line)

    if ratio:
        name, diff = nearest_ratio(ratio)
        if diff > RATIO_TOLERANCE:
            print(f"[!] Unusual aspect ratio ({ratio:.3f}).")
            print("[!] If the image looks squished: Settings -> Aspect Ratio -> Force 16:9")

    fix_aspect(filepath, mode)


# ------------------------------------------- Download with Stall Detection

def _pipe_reader(pipe, q):
    """Reads lines from a pipe and puts them in a queue."""
    try:
        for line in iter(pipe.readline, ""):
            q.put(line)
    except Exception:
        pass
    finally:
        q.put(None)


def _run_process_with_stall_check(cmd, on_line) -> int:
    """Runs a subprocess, calls on_line(line) for each output line, and aborts on stall."""
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        encoding="utf-8",
        errors="replace",
    )

    q = queue.Queue()
    reader = threading.Thread(target=_pipe_reader, args=(process.stdout, q), daemon=True)
    reader.start()

    last_activity = time.time()

    while True:
        if process.poll() is not None and q.empty():
            break

        try:
            line = q.get(timeout=1)
        except queue.Empty:
            if time.time() - last_activity > STALL_TIMEOUT:
                print(f"\n[-] Stall detected: no progress for {STALL_TIMEOUT}s. Aborting.")
                process.kill()
                return 998
            continue

        if line is None:
            if process.poll() is not None:
                break
            continue

        last_activity = time.time()
        line = line.strip()
        if line and on_line(line) is False:
            break

    print()
    return process.returncode


def _run_ytdlp_with_progress(cmd) -> int:
    """Runs yt-dlp, shows progress, aborts on stall."""
    last_percent = -1

    def on_line(line: str):
        nonlocal last_percent
        m = re.search(r'\[download\]\s+(\d+\.?\d*)%', line)
        if m:
            percent = float(m.group(1))
            if percent != last_percent:
                last_percent = percent
                print(f"\r{line[:110]}    ", end="", flush=True)
        elif "error" in line.lower() or "warning" in line.lower():
            print(f"\n[!] {line[:110]}")

    return _run_process_with_stall_check(cmd, on_line)


def _run_ffmpeg_with_progress(cmd) -> int:
    """Runs ffmpeg, shows progress, aborts on stall."""
    total_duration = None
    start_time = time.time()
    last_print = 0

    def on_line(line: str):
        nonlocal total_duration, last_print
        if "Duration:" in line and total_duration is None:
            try:
                match = re.search(r'Duration:\s*(\d+):(\d+):(\d+\.?\d*)', line)
                if match:
                    h, m_, s = float(match.group(1)), float(match.group(2)), float(match.group(3))
                    total_duration = h * 3600 + m_ * 60 + s
                    print(f"[+] Duration detected: {format_time(int(total_duration))}")
            except (ValueError, TypeError):
                pass

        if line.startswith("out_time_ms="):
            try:
                microseconds = int(line.split("=")[1])
                current_time = microseconds / 1_000_000

                if total_duration and total_duration > 0:
                    progress = min(100, (current_time / total_duration) * 100)
                    elapsed = time.time() - start_time

                    if elapsed - last_print > 2 and progress > 0 and elapsed > 0:
                        eta = (elapsed / progress) * (100 - progress)
                        speed = current_time / elapsed
                        print(
                            f"\r[*] {progress:5.1f}% | "
                            f"{format_time(int(current_time))}/{format_time(int(total_duration))} | "
                            f"ETA: {format_time(int(eta))} | "
                            f"Speed: {speed:.1f}x    ",
                            end="", flush=True,
                        )
                        last_print = elapsed
            except (ValueError, TypeError):
                pass

        if line.startswith("progress=end"):
            print("\n[+] ffmpeg finished")
            return False

    return _run_process_with_stall_check(cmd, on_line)


def download_video(video_url: str, filepath: Path, resume: bool = True) -> int:
    """Downloads a video. yt-dlp first (with referer), ffmpeg as fallback."""

    print("[*] Downloading with yt-dlp (incl. referer header)...")
    cmd = [
        "yt-dlp",
        "--referer", VOE_REFERER,
        "--user-agent", Config.USER_AGENT,
        "--socket-timeout", "15",
        "--retries", "3",
        "--continue" if resume else "--no-continue",
        *([] if resume else ["--no-part"]),
        "--newline",
        "-o", str(filepath),
        video_url,
    ]
    result = _run_ytdlp_with_progress(cmd)
    if result == 0:
        return 0

    # Fallback: ffmpeg with referer header and timeout
    if ".m3u8" in video_url:
        print("[*] yt-dlp failed, trying ffmpeg with referer...")
        cmd = [
            "ffmpeg",
            "-user_agent", Config.USER_AGENT,
            "-headers", f"Referer: {VOE_REFERER}\r\n",
            "-rw_timeout", "20000000",
            "-i", video_url,
            "-c", "copy",
            "-bsf:a", "aac_adtstoasc",
            "-movflags", "+faststart",
            "-progress", "pipe:1",
            "-nostats",
            "-y", str(filepath),
        ]
        result = _run_ffmpeg_with_progress(cmd)

    return result


# ------------------------------------------------------- Download

def download_one_episode(page, episode_data, provider, download_dir, series_title,
                         preferred_quality="1080p", resume=True, skip_existing=True,
                         aspect_mode=ASPECT_CHECK):
    """Downloads a single episode and checks the format afterwards."""
    video_urls = []

    def handle_response(response):
        url = response.url
        if any(h in url for h in IGNORED_HOSTS):
            return
        if ".m3u8" in url or ".mp4" in url:
            if url not in video_urls:
                video_urls.append(url)

    page.on("response", handle_response)

    try:
        season = episode_data.get("season", 1)
        number = episode_data.get("number", 0)
        title = sanitize_filename(episode_data.get("title", f"Episode_{number}"))
        series = sanitize_filename(series_title)

        filename = f"{series}_S{season:02d}E{number:02d}_{title}.mp4"
        filepath = Path(download_dir) / filename

        if skip_existing and filepath.exists() and filepath.stat().st_size > 0:
            print(f"[✓] Skipped (already exists): {filename}")
            return "skipped"

        print(f"[*] Opening: {episode_data['url']}")
        page.goto(episode_data["url"], wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(2000)

        selector = f"button[data-provider-name='{provider}']"
        try:
            page.wait_for_selector(selector, timeout=10000)
            print(f"[*] Clicking {provider} button...")
            page.click(selector, force=True)
        except Exception:
            print(f"[!] {provider} button missing, using fallback...")
            fallback = page.locator(
                "button[data-provider-name][data-language-label='Deutsch']"
            ).first
            if fallback.count() == 0:
                print("[-] No German host button found.")
                return "failed"
            used = fallback.get_attribute("data-provider-name")
            print(f"[+] Using instead: {used}")
            fallback.click(force=True)

        print("[*] Waiting for video URL (max 50s)...")
        print("[!] If a captcha appears: solve it manually in the browser window.")
        for remaining in range(50, 0, -1):
            if video_urls:
                break
            page.wait_for_timeout(1000)
            if remaining % 10 == 0:
                print(f"[*] {remaining}s remaining...")

        if not video_urls:
            for sel in (
                "button.jw-icon-display", ".jw-icon-display", "video",
                ".play-button", "button:has-text('Play')",
            ):
                try:
                    btn = page.locator(sel).first
                    if btn.count() > 0 and btn.is_visible():
                        print(f"[*] Clicking play ({sel})...")
                        btn.click(force=True)
                        for _ in range(15):
                            if video_urls:
                                break
                            page.wait_for_timeout(1000)
                        if video_urls:
                            break
                except Exception:
                    continue

        if not video_urls:
            print("[-] Timeout: No video URL found.")
            return "failed"

        video_url = pick_best_url(video_urls, preferred_quality)
        print(f"[+] Selected: {video_url[:90]}...")

        result = download_video(video_url, filepath, resume=resume)

        if result == 0 and filepath.exists() and filepath.stat().st_size > 0:
            print(f"[+] Done: {filename} ({format_size(filepath.stat().st_size)})")
            verify_episode(filepath, aspect_mode)
            return "success"

        # Clean up empty files for clean resume
        try:
            if filepath.exists() and filepath.stat().st_size == 0:
                filepath.unlink()
        except OSError:
            pass

        print(f"[-] Download failed (code {result})")
        return "failed"

    except Exception as e:
        print(f"[-] Error: {e}")
        return "failed"

    finally:
        try:
            page.remove_listener("response", handle_response)
        except Exception:
            pass


def run_download(episodes, provider, series_title, download_dir,
                 preferred_quality="1080p",
                 resume=True, skip_existing=True, notify=True,
                 aspect_mode=ASPECT_CHECK):
    """Downloads episodes sequentially using a persistent browser session."""
    Path(download_dir).mkdir(parents=True, exist_ok=True)
    user_data_dir = os.path.join(os.getcwd(), "playwright_data")

    start_time = time.time()
    results = {"success": 0, "failed": 0, "skipped": 0}

    with sync_playwright() as p:
        context = build_browser_context(p, user_data_dir)

        if not check_login_status(context):
            print("[!] Login required. Download aborted.")
            context.close()
            return 0, len(episodes), 0

        page = context.new_page()

        total = len(episodes)

        for i, ep in enumerate(episodes, 1):
            print("\n" + "=" * 60)
            print(
                f"[*] Episode {i}/{total}: "
                f"S{ep.get('season', 1):02d}E{ep.get('number', 0):02d} "
                f"- {ep.get('title', '')}"
            )
            print("=" * 60)

            result = download_one_episode(
                page, ep, provider, download_dir, series_title,
                preferred_quality, resume, skip_existing, aspect_mode,
            )

            if result == "success":
                results["success"] += 1
            elif result == "skipped":
                results["skipped"] += 1
            else:
                results["failed"] += 1

            if i < total:
                print(f"\n[*] Continuing with episode {i + 1} in 3s...")
                time.sleep(3)

        context.close()

    total_time = time.time() - start_time

    print("\n" + "=" * 60)
    print("[*] Download complete!")
    print(f"[*] Successful: {results['success']}")
    print(f"[*] Skipped: {results['skipped']}")
    print(f"[*] Failed: {results['failed']}")
    print(f"[*] Total time: {format_time(int(total_time))}")
    print(f"[*] Folder: {download_dir}")
    print("=" * 60)

    if notify and results["success"] > 0:
        send_notification(
            "Download complete!",
            f"{results['success']} episodes downloaded successfully.\n"
            f"Duration: {format_time(int(total_time))}",
        )

    return results["success"], results["failed"], results["skipped"]


# ------------------------------------------------------- Scraping

def resolve_episodes(scraper, target_url):
    """Breaks a URL into (series_title, episodes, kind)."""
    is_series = "/staffel-" not in target_url and "/episode-" not in target_url
    is_season = "/staffel-" in target_url and "/episode-" not in target_url

    if is_series:
        series_url = target_url
    elif is_season:
        series_url = re.sub(r"/staffel-\d+.*$", "", target_url)
    else:
        series_url = re.sub(r"/staffel-\d+/episode-\d+.*$", "", target_url)

    series_title = scraper.get_series_title(series_url)
    if not series_title:
        m = re.search(r"/serie[s]?/([^/]+)", target_url)
        series_title = m.group(1) if m else "Unknown_Series"

    if is_series:
        return series_title, None, "series"

    if is_season:
        eps = scraper.parse_season(target_url)
        m = re.search(r"/staffel-(\d+)", target_url)
        season = int(m.group(1)) if m else 1
        for e in eps:
            e["season"] = season
        return series_title, eps, "season"

    m_ep = re.search(r"/episode-(\d+)", target_url)
    m_se = re.search(r"/staffel-(\d+)", target_url)
    num = int(m_ep.group(1)) if m_ep else 1
    season = int(m_se.group(1)) if m_se else 1
    return series_title, [{
        "number": num,
        "title": f"Episode {num}",
        "url": target_url,
        "season": season,
    }], "episode"


def ask_seasons(scraper, target_url):
    """For a series URL, asks which seasons to load."""
    seasons = scraper.parse_series(target_url)
    if not seasons:
        print("[!] No seasons found.")
        return []

    print(f"[*] {len(seasons)} seasons found:")
    for s in seasons:
        print(f"    Season {s['number']}")

    print("\nOptions:  all | 1,3,5 | 2-4")
    choice = input("\n>>> Which seasons to load? ").strip().lower()

    if choice == "all" or not choice:
        picked = seasons
    elif "-" in choice:
        try:
            a, b = (int(x) for x in choice.split("-", 1))
            picked = [s for s in seasons if a <= s["number"] <= b]
        except ValueError:
            print("[!] Invalid range, loading all seasons.")
            picked = seasons
    else:
        nums = {int(n.strip()) for n in choice.split(",") if n.strip().isdigit()}
        picked = [s for s in seasons if s["number"] in nums]

    episodes = []
    for season in picked:
        print(f"\n[*] Loading episodes for season {season['number']}...")
        eps = scraper.parse_season(season["url"])
        for e in eps:
            e["season"] = season["number"]
        episodes.extend(eps)
        print(f"[*] {len(eps)} episodes found.")

    return episodes


def collect_providers(scraper, episode_url):
    """Lists available German providers for an episode."""
    data = scraper.parse_episode(episode_url)
    providers = []
    for h in data["hosts"]:
        if h.get("language") == "Deutsch" and h["provider"] not in providers:
            providers.append(h["provider"])
    return providers
