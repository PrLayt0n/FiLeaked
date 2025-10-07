# FiLeaked — Fingerprinted File Distribution & Leak Detection System

> **FastAPI backend to distribute uniquely fingerprinted files and pinpoint the source of leaked copies.**
> Supports **PDF**, **PNG**, and **TXT** via invisible watermarks and metadata. Runs on a single VPS with **local Postgres** and **no third-party services**.

---

## Table of Contents

* [Overview](#overview)
* [How It Works](#how-it-works)
* [Features](#features)
* [Architecture](#architecture)
* [API](#api)

  * [/api/distribute](#post-apidistribute)
  * [/api/scan](#post-apiscan)
  * [/admin/distributions](#get-admindistributions)
* [Fingerprinting Techniques](#fingerprinting-techniques)
* [Security Design](#security-design)
* [Configuration](#configuration)
* [Local Development (Docker Compose)](#local-development-docker-compose)
* [Production Deployment (VPS)](#production-deployment-vps)
* [Usage Examples](#usage-examples)
* [Tips, Warnings & Limitations](#tips-warnings--limitations)
* [Backup & Recovery](#backup--recovery)
* [Roadmap](#roadmap)
* [FAQ](#faq)
* [License](#license)

---

## Overview

**FiLeaked** is a backend service for **distributing files** with **unique, invisible fingerprints** (per recipient) and for **detecting leaks** by extracting those fingerprints later. It’s designed for developers and sysadmins who share sensitive documents and want traceability if a file escapes.

Typical scenarios:

* Share confidential PDFs or images with partners/clients.
* Send internal memos to teams.
* Distribute reports where every copy must be uniquely identifiable.

If a copy appears in the wild, upload it to FiLeaked to **identify which recipient** it was issued to.

---

## How It Works

1. **Distribute**: Upload a file + recipient → FiLeaked embeds a **secure token** invisibly and stores the fingerprinted copy.
2. **Leak appears**: You obtain the suspicious file.
3. **Scan**: Upload the file to `/api/scan` → FiLeaked extracts & decrypts the fingerprint → returns the **matching distribution record**.

---

## Features

* **FastAPI** app (ASGI), high-performance REST endpoints.
* **Local PostgreSQL** for distribution records.
* **Local filesystem storage** for originals + fingerprinted copies.
* **Multiple fingerprint layers** per type (metadata + content steganography).
* **AES-GCM encryption** of tokens; optional **HMAC-SHA256** signatures.
* **API key** auth + optional rate limiting (at reverse proxy).
* **Admin listing** of distributions.
* **No external services** required; deploy on a single VPS (1 vCPU, 1–2 GB RAM).

---

## Architecture

```
[Client/Admin] ── HTTPS ──> [Nginx] ──> [Gunicorn + Uvicorn] ──> [FastAPI: FiLeaked]
                                                │
                                         [Local Filesystem]
                                                │
                                            [PostgreSQL]
```

* **Service**: FastAPI app encapsulates fingerprinting & scanning logic.
* **DB**: Postgres stores file + distribution metadata and fingerprint references.
* **Storage**: Files are kept on disk (configurable path).
* **Proxy**: Nginx terminates TLS, proxies to a Unix socket or localhost port.

---

## API

All endpoints require an API key (e.g., header `X-API-KEY: <your_key>` or `Authorization: Bearer <your_key>` depending on your configuration).

### POST `/api/distribute`

Create a recipient-specific, fingerprinted copy.

**Form fields**

* `file` *(required)*: uploaded file (`pdf`, `png`, or `txt`)
* `recipient` *(required)*: string identifier (email, user ID, etc.)

**Response**

```json
{
  "distribution_id": "uuid",
  "file_id": "uuid",
  "recipient": "alice@example.com",
  "created_at": "2025-10-07T22:16:00Z",
  "download_url": "https://your.domain/files/<file_id>"
}
```

---

### POST `/api/scan`

Scan a suspected leaked file and identify the source.

**Form fields**

* `file` *(required)*: uploaded file (`pdf`, `png`, or `txt`)

**Response (match found)**

```json
{
  "match": true,
  "distribution_id": "uuid",
  "file_id": "uuid",
  "recipient": "alice@example.com",
  "created_at": "2025-10-07T22:16:00Z",
  "techniques_detected": ["pdf.xmp", "pdf.invisible_text"]
}
```

**Response (no match)**

```json
{ "match": false }
```

---

### GET `/admin/distributions`

Protected admin listing of distributions with pagination.

**Query**

* `page`, `page_size` (optional)

**Response**

```json
{
  "items": [
    {
      "distribution_id": "uuid",
      "file_id": "uuid",
      "original_filename": "report.pdf",
      "recipient": "alice@example.com",
      "created_at": "2025-10-07T22:16:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 50
}
```

---

## Fingerprinting Techniques

### PDF

* **Metadata**: custom keys in Info/XMP carrying encrypted token.
* **Invisible text**: tiny/white text or zero-width sequences placed unobtrusively.
* **Extraction**: parse metadata + text content; decrypt & verify token.

### PNG

* **Metadata**: `tEXt` / `iTXt` chunks with encrypted token.
* **LSB steganography**: bit-level embedding across selected pixels.
* **Extraction**: read metadata; reconstruct bits from known pixel pattern.

### TXT

* **Zero-width characters**: encode bits with U+200B etc.
* **Format comments** (where allowed): e.g., HTML/XML/INI comments.
* **Extraction**: scan codepoints/comments; decode & verify token.

> Multiple techniques can be combined so at least one survives simple transformations.

---

## Security Design

* **Master secret** (`MASTER_SECRET`, 256-bit): root key for cryptography.
* **AES-GCM**: encrypts token payloads (confidentiality + integrity).
* **HMAC-SHA256**: optional defense-in-depth for IDs or API tokens.
* **API authentication**: single key or multiple keys (hashed in DB).
* **Hardening**: file type checks, size limits, throttling (via Nginx), audit logs.
* **Secrets in env**: never hardcode; load via settings.

---

## Configuration

Set via environment variables (e.g., `.env` or systemd `EnvironmentFile`):

| Variable                  | Description                                          | Example                                             |
| ------------------------- | ---------------------------------------------------- | --------------------------------------------------- |
| `MASTER_SECRET`           | 32-byte (256-bit) secret for crypto (hex or base64). | `8b...`                                             |
| `DATABASE_URL` / `DB_URL` | Postgres DSN.                                        | `postgresql://user:pass@localhost:5432/fileaked_db` |
| `API_KEY`                 | API key for clients/admin scripts.                   | `s3cr3t`                                            |
| `FILE_STORAGE_PATH`       | Directory for originals + fingerprinted copies.      | `/var/lib/fileaked/files`                           |
| `MAX_FILE_SIZE_MB`        | Upload size cap.                                     | `50`                                                |
| `OPENAPI_ENABLED`         | Enable docs in dev only (disable in prod).           | `false`                                             |

Generate a strong secret:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## Local Development (Docker Compose)

> Run the app + Postgres locally without installing system packages.

**docker-compose.yml** (sketch)

```yaml
services:
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: fileaked_user
      POSTGRES_PASSWORD: somepassword
      POSTGRES_DB: fileaked_db
    volumes:
      - postgres_data:/var/lib/postgresql/data
  web:
    build: .
    depends_on: [db]
    environment:
      DATABASE_URL: postgresql://fileaked_user:somepassword@db:5432/fileaked_db
      MASTER_SECRET: <dev-secret>
      API_KEY: <dev-api-key>
      FILE_STORAGE_PATH: /data/files
    volumes:
      - ./:/code:ro
      - files_data:/data/files
    ports:
      - "8000:80"
volumes:
  postgres_data:
  files_data:
```

**Run**

```bash
docker-compose up --build
# API at http://localhost:8000 (docs if enabled)
```

---

## Production Deployment (VPS)

1. **Server prep**

   ```bash
   sudo apt update && sudo apt upgrade -y
   sudo apt install -y python3 python3-venv python3-pip build-essential git postgresql nginx
   ```

2. **Database**

   ```bash
   sudo -u postgres psql -c "CREATE USER fileaked_user WITH PASSWORD 'StrongPassword';"
   sudo -u postgres psql -c "CREATE DATABASE fileaked_db OWNER fileaked_user;"
   ```

3. **App setup**

   ```bash
   sudo adduser --system --group fileaked
   sudo mkdir -p /opt/fileaked /opt/fileaked/files
   sudo chown -R fileaked:fileaked /opt/fileaked
   cd /opt/fileaked
   # copy project files here
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Environment**

   ```
   /opt/fileaked/.env
   MASTER_SECRET=...
   DATABASE_URL=postgresql://fileaked_user:StrongPassword@localhost:5432/fileaked_db
   API_KEY=...
   FILE_STORAGE_PATH=/opt/fileaked/files
   MAX_FILE_SIZE_MB=50
   ```

5. **Systemd (Gunicorn + Uvicorn)**

   ```
   /etc/systemd/system/fileaked.service
   ```

   ```
   [Unit]
   Description=FiLeaked Service
   After=network.target

   [Service]
   User=fileaked
   WorkingDirectory=/opt/fileaked
   EnvironmentFile=/opt/fileaked/.env
   ExecStart=/opt/fileaked/venv/bin/gunicorn -w 2 -k uvicorn.workers.UvicornWorker -b unix:/opt/fileaked/fileaked.sock app:app
   Restart=on-failure
   RestartSec=5s

   [Install]
   WantedBy=multi-user.target
   ```

   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now fileaked
   ```

6. **Nginx reverse proxy (with large uploads & rate limit snippets)**

   ```
   /etc/nginx/sites-available/fileaked
   ```

   ```nginx
   server {
     listen 80;
     server_name fileaked.example.com;

     client_max_body_size 100M;

     location / {
       proxy_pass http://unix:/opt/fileaked/fileaked.sock:;
       proxy_set_header Host $host;
       proxy_set_header X-Real-IP $remote_addr;
       proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
       proxy_set_header X-Forwarded-Proto $scheme;
     }
   }
   ```

   ```bash
   sudo ln -s /etc/nginx/sites-available/fileaked /etc/nginx/sites-enabled/
   sudo rm -f /etc/nginx/sites-enabled/default
   sudo nginx -t && sudo systemctl reload nginx
   ```

7. **HTTPS (Let’s Encrypt)**

   ```bash
   sudo apt install -y certbot python3-certbot-nginx
   sudo certbot --nginx -d fileaked.example.com
   sudo certbot renew --dry-run
   ```

8. **Firewall**

   ```bash
   sudo ufw allow 80,443/tcp
   sudo ufw enable
   ```

---

## Usage Examples

**Distribute a PDF to Alice**

```bash
curl -H "X-API-KEY: $API_KEY" \
  -F "file=@report.pdf" \
  -F "recipient=alice@example.com" \
  https://fileaked.example.com/api/distribute
```

**Scan a suspected leak**

```bash
curl -H "X-API-KEY: $API_KEY" \
  -F "file=@leaked.pdf" \
  https://fileaked.example.com/api/scan
```

**List distributions (admin)**

```bash
curl -H "Authorization: Bearer $API_KEY" \
  "https://fileaked.example.com/admin/distributions?page=1&page_size=50"
```

---

## Tips, Warnings & Limitations

* **Transformations may strip fingerprints**:

  * PDFs: re-saving/printing to PDF, metadata cleaners, “remove hidden info” can remove marks.
  * PNGs: LSB bits are **not robust** to lossy compression (JPEG), heavy edits, resizing, screenshots.
  * TXT: copy/paste often drops zero-width chars; converting formats can remove comments.
* **Goal**: catch careless leaks; **cannot** prevent retyping or photographing content.
* **Defense-in-depth**: combine with visible watermarks, legal notices, and access policies.
* **High-stakes docs**: consider multiple delivery controls; assume experts can remove watermarks but **cannot forge** valid tokens without the secret.

---

## Backup & Recovery

* **Back up**: PostgreSQL (e.g., nightly `pg_dump`) and the **`MASTER_SECRET`** (secure vault).
* Losing the DB breaks mapping from fingerprints → recipients.
* Rotating `MASTER_SECRET` invalidates decryption of older fingerprints unless you keep previous keys for reads.

---

## Roadmap

* Additional file types (DOCX, PPTX, audio/video fragments).
* More robust (perceptual) image watermarking options.
* Admin web UI with search, per-recipient audit views.
* Multi-tenant API keys and scoped roles.
* Optional at-rest encryption for stored files.

---

## FAQ

**Does FiLeaked stop leaks?**
No. It **traces** leaked files by embedding a unique, invisible, cryptographically protected fingerprint.

**Will users notice?**
Fingerprints are invisible and designed to avoid visual changes. Files may grow slightly in size.

**Can attackers forge someone else’s fingerprint?**
Not feasibly. Tokens are encrypted (AES-GCM) and optionally signed (HMAC). They can try to remove marks, but forging a valid new one requires the secret.

**What if a file is re-encoded or screenshotted?**
Some techniques won’t survive; that’s expected. Use visible watermarks + policy for stronger deterrence.

**Should I tell recipients files are fingerprinted?**
Yes—notification is often a strong deterrent and may be a policy/legal requirement.

Thanks for looking at my project!
