# zChit Backend

FastAPI backend for the zChit fund management platform.

## Development

1. Activate the virtual environment.
2. Install dependencies from `requirements.txt`.
3. Run `uvicorn app.main:app --reload` from this directory.

API documentation is available at `http://127.0.0.1:8000/docs`.

## Authentication

Endpoints are available under `/api/v1/auth`:

- `POST /register`
- `POST /verify-email`
- `POST /resend-verification`
- `POST /login`
- `POST /forgot-password`
- `POST /reset-password`

Copy `.env.example` to `.env` and configure secure JWT/OTP secrets plus the
ZeptoMail send token and verified sender address. Passwords and OTPs are stored
only as hashes.

Run integration tests with `.venv/bin/python -m pytest tests/test_auth.py -q`.

## Company onboarding

Owner-authenticated endpoints are available under `/api/v1/companies`:

- `POST /` — create one company for the authenticated owner
- `GET /me` — retrieve the owner's company
- `POST /me/logo` — upload a PNG, JPEG, or WebP logo up to 5 MB

Onboarding generates an immutable `ZCH-XXXXXXXXXX` company code and accepts
company/legal names, phone, email, GSTIN, PAN, website, and one or more structured
addresses. Uploaded logos are served under `/uploads`.
