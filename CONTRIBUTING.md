# Contributing to StreamBox

Thank you for your interest in contributing to **StreamBox (ssto-dl)**!

## How Can I Contribute?

### Reporting Bugs
- Check existing [Issues](https://github.com/toto9251/StreamBox/issues) before opening a new one.
- Use the **Bug Report** issue template and include your OS, Python version, and full error output.
- **Never** include personal credentials (`auth_credentials.json`) or `.env` files in bug reports.

### Suggesting Enhancements
- Use the **Feature Request** issue template to describe the proposed feature and why it would be useful.

### Pull Requests
1. Fork the repository and create a new branch from `main`.
2. Keep changes focused and clean; follow the existing code style.
3. Verify that all Python files compile without errors:
   ```bash
   python -m py_compile config.py main.py manual_auth.py menu.py pipeline.py scraper.py search.py settings.py
   ```
4. Open a Pull Request and fill out the PR template.

## Development Setup

```bash
git clone https://github.com/toto9251/StreamBox.git
cd StreamBox
python -m venv venv
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
pip install -e .
```
