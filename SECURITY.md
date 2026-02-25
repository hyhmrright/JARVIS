[English](SECURITY.md) | [中文](docs/i18n/zh/SECURITY.md)

# Security Policy

## Reporting a Vulnerability

**Please do NOT open a public issue for security vulnerabilities.**

If you discover a security vulnerability in JARVIS, please report it responsibly:

1. **GitHub Private Vulnerability Reporting (Preferred)**
   Go to the [Security tab](https://github.com/hyhmrright/JARVIS/security/advisories/new) of this repository
   and click "Report a vulnerability".

2. **Email**
   Send details to **hyhmrright@gmail.com**.

Please include:
- A description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

## Response Timeline

| Action | Timeline |
|--------|----------|
| Acknowledgment | Within 72 hours |
| Initial assessment | Within 1 week |
| Fix release | Depends on severity |

## Supported Versions

| Version | Supported |
|---------|-----------|
| Latest on `main` | Yes |
| `dev` branch | Best effort |
| Older releases | No |

## Scope

This policy applies to:

- JARVIS backend (FastAPI, Python)
- JARVIS frontend (Vue 3, TypeScript)
- Docker configuration and deployment
- Authentication and encryption (JWT, bcrypt, Fernet)
- Database access and API endpoints
