# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| `main` (deployed demo) | Best-effort |
| Older commits | No guaranteed security patches |

This repository is maintained as an engineering project with a public demo. Treat the demo as non-production.

## Reporting a vulnerability

- Do **not** open a public issue for credential leaks, auth bypasses, or data exposure.
- Prefer a private report to the repository owner (GitHub Security Advisories if enabled, or a private contact already used for this project).
- Include: affected component, reproduction steps, impact, and whether secrets were exposed.

## Responsible disclosure

- Allow reasonable time for a fix before public disclosure.
- Do not access other users’ data, production databases, or third-party services beyond minimal proof on your own accounts.
- Do not publish credentials, tokens, JWT secrets, Cloudinary keys, Firebase service accounts, or database URLs in issues, PRs, or screenshots.

## Repository hygiene

Expected controls in this project:

- `.env` / `.env.*` (except examples) are gitignored
- `.env.example` files contain variable **names** only (placeholder values)
- No service-account JSON or private keys in git history for new commits
- Face images and student PII must not be committed

If you discover a secret in git history, report it privately and rotate the secret immediately.
