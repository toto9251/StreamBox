# 🎬 StreamBox (ssto-dl)

An automated and interactive downloader for movies and series from SerienStream.to, featuring an interactive terminal UI, automatic episode resolution, format/aspect-ratio verification, resume support, and anti-bot protection handling.

---

## ✨ Features

- 🔍 **Interactive Search & CLI Mode**: Search for any movie/series with instant caching, or paste any URL directly.
- 📦 **Full Series, Seasons or Single Episodes**: Download entire series at once, select specific seasons (e.g. `1,3,5` or `2-4`), or choose individual episodes with interactive multi-select.
- 🤖 **Persistent Login & Captcha Assistance**: Solves initial verification in a browser session; subsequent episodes run automatically.
- 📺 **Aspect Ratio & Format Diagnostics**: Verifies display aspect ratio and metadata via `ffprobe` and corrects non-square SAR/stretch issues via `ffmpeg` (lossless, metadata-only without re-encoding).
- ⚡ **Resume & Skip Existing**: Automatically resumes downloads and skips already completed files.
- 🌐 **Multiple Hosters Supported**: VOE (default/fastest), Doodstream, Streamtape, and Vidoza.
- 💻 **100% Portable**: No hardcoded system paths; runs seamlessly on any user account or directory structure across Windows, macOS, and Linux.

---

## 📋 System Requirements

1. **Python 3.10+**: Available from [python.org](https://www.python.org/downloads/) (on Windows, check *"Add Python to PATH"* during installation).
2. **FFmpeg**: Required for stream merging and format verification.
   - **Windows**: `winget install Gyan.FFmpeg` or download from [gyan.dev/ffmpeg](https://www.gyan.dev/ffmpeg/builds/)
   - **macOS**: `brew install ffmpeg`
   - **Linux**: `sudo apt install ffmpeg`

---

## 🚀 Quick Start (Automated 1-Click Setup)

### Windows
Simply double-click:
```bat
start.bat
```
*(If it's your first time running, `start.bat` will automatically trigger `setup.bat` to create the virtual environment and install all dependencies!)*

Or manually run:
```bat
setup.bat
```

### Linux & macOS
Make the scripts executable and launch:
```bash
chmod +x setup.sh start.sh
./start.sh
```

---

## 🎮 Usage

### 1. Interactive Menu Mode
Simply launch the application without arguments:
```bash
python main.py
```
*(or double-click `start.bat` on Windows)*

The interactive menu will let you:
- Search for titles with instant fuzzy matching.
- Paste URLs directly.
- Configure download paths, qualities, and aspect ratio correction.
- Refresh the series cache.

### 2. Direct CLI Mode
Pass a series, season, or episode URL directly as a command-line argument:

```bash
# Entire series:
python main.py https://serienstream.to/serie/breaking-bad

# Specific season:
python main.py https://serienstream.to/serie/breaking-bad/staffel-1

# Single episode:
python main.py https://serienstream.to/serie/breaking-bad/staffel-1/episode-1
```

### 3. Login Setup (Optional)
To log in with your SerienStream account:
```bash
python manual_auth.py
```
This opens a browser window and securely stores the authenticated session in your local `playwright_data/` directory (which is strictly git-ignored).

---

## 📁 Repository Structure

```
ssto-dl/
├── config.py           # Base domains and User-Agent configuration
├── main.py             # Application entry point (Menu & CLI handler)
├── manual_auth.py      # Account authentication & session setup
├── menu.py             # Interactive Rich/Questionary terminal UI
├── pipeline.py         # Download pipeline, yt-dlp/ffmpeg engine, format probe
├── scraper.py          # HTML parser and episode resolver
├── search.py           # Series catalog search with persistent caching
├── settings.py         # Config & preference management (cross-platform)
├── pyproject.toml      # Package specification & dependencies
├── requirements.txt    # Fallback dependency list
├── setup.bat / .sh     # 1-click automated setup scripts
├── start.bat / .sh     # 1-click launcher scripts
└── .gitignore          # Keeps your login & download data 100% private
```

---

## 🔒 Privacy & Security

- **Private by Design**: Your `auth_credentials.json`, browser session directories (`playwright_data/`), downloaded media files (`downloads/`), and `.env` files are specified in `.gitignore` and are **never** committed or pushed to GitHub.

---

## ⚖️ Disclaimer

This software is for educational and personal archival purposes only. Please respect copyright laws and the terms of service of any third-party providers.
