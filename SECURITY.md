# Security Policy

## Supported Versions

Only the latest version on the `main` branch is actively supported with security updates.

| Version | Supported |
| ------- | --------- |
| 2.0.x   | Yes       |
| < 2.0   | No        |

## Reporting a Vulnerability

If you discover a security vulnerability in **StreamBox**, please do **not** open a public issue with sensitive details.

Instead:
- Use GitHub's **Private Vulnerability Reporting** feature under the repository's **Security** tab (if enabled), or
- Contact the repository maintainer (`toto9251`) directly via GitHub.

Please include:
- A description of the vulnerability and potential impact.
- Steps to reproduce the issue.

## User Privacy Note

- Local credentials (`auth_credentials.json`), `.env` files, and browser session directories (`playwright_data/`) are excluded via `.gitignore`. Never commit or share these files.
