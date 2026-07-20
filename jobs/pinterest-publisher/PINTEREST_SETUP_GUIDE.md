# 📌 Pinterest Automation & Setup Guide (`pinterest-publisher`)

A complete reference guide for automated daily Pinterest publishing for **Color It Daily** (`coloritdaily.com`) using **Buffer's official GraphQL API** and **Gemini 3.5 Flash**.

---

## 🌟 Overview

The `pinterest-publisher` service runs as an isolated, standalone Cloud Run Function microservice. It operates on a separate schedule and will **never cause image generation or website publishing to fail**.

### Key Features:
* **Gemini 3.5 Flash Copywriting**: Crafts high-converting Pin titles, parent/teacher-oriented descriptions, and targeted hashtags.
* **Buffer Official GraphQL API**: Posts directly to Pinterest via Buffer's pre-approved integration (`https://api.buffer.com`). Zero developer app review required.
* **Strict 500-Char Limit Safety**: Enforces Pinterest's hard limit so posts are never truncated or rejected.
* **State Management**: Updates Firestore (`pinterest_published: True`, `pinterest_pin_id`, `pinterest_published_at`) to ensure no page is ever published twice.
* **Local CLI Testing**: Built-in `argparse` support for local testing with `--dry-run`, `--force`, `--limit`, and `--doc-id`.
* **Board ID Extractor Tool**: Helper script (`get_board_id.py`) to automatically extract numeric Board IDs from any Pinterest URL.

---

## 🚀 Quick Start Setup (3 Steps)

### Step 1: Connect Pinterest to Buffer (1 Minute)
1. Sign up for a free account at **[buffer.com](https://buffer.com)**.
2. Click **Add Channels** → Select **Pinterest** → Click **Authorize**.
3. Your Pinterest Business account is now connected in 1 click!

### Step 2: Get API Key & Profile ID
1. Go to **[account.buffer.com/access-tokens](https://account.buffer.com/access-tokens)** (or **Buffer Settings → Developer / Access Tokens**).
2. Click **Generate API Key** → Copy your key (`BUFFER_ACCESS_TOKEN`).
3. Open your Pinterest channel in Buffer ([publish.buffer.com](https://publish.buffer.com)) and check the URL:
   `https://publish.buffer.com/channels/6a5d454ce2638b94d79a0839/settings`  
   The ID after `/channels/` (e.g., `6a5d454ce2638b94d79a0839`) is your **`BUFFER_PROFILE_ID`**.

### Step 3: Get Numeric Pinterest Board ID
Use our built-in helper utility to extract your numeric Pinterest Board ID from any Pinterest URL or shortlink:

```bash
python jobs/pinterest-publisher/get_board_id.py "https://ca.pinterest.com/olivierstamand1/free-printable-coloring-pages-for-kids/"
```

It will automatically output:
`👉 Recommended PINTEREST_BOARD_ID='1112952195355406164'`

---

## ⚙️ Environment Variables

Add these to your root `.env` or deployment variables:

```env
# Enable Pinterest Publishing (true / false)
PINTEREST_ENABLED=true

# Buffer API Integration
BUFFER_ACCESS_TOKEN='your_buffer_api_key'
BUFFER_PROFILE_ID='6a5d454ce2638b94d79a0839'

# Pinterest Board ID
PINTEREST_BOARD_ID='1112952195355406164'

# Multi-Board Routing (Optional)
PINTEREST_BOARD_MAP='{}'

# Website Base URL
WEBSITE_BASE_URL='https://coloritdaily.com'

# Gemini Copywriting Model
PINTEREST_GEMINI_MODEL='gemini-3.5-flash'
```

---

## 🧪 Local Testing & CLI Usage

You can test the script locally using CLI flags:

```bash
# 1. Run in dry-run mode (simulates Pin creation without sending API request)
python jobs/pinterest-publisher/main.py --dry-run

# 2. Extract numeric Board ID from any Pinterest URL
python jobs/pinterest-publisher/get_board_id.py <PINTEREST_BOARD_URL>

# 3. Test a specific Firestore Document ID
python jobs/pinterest-publisher/main.py --dry-run --doc-id <FIRESTORE_DOC_ID>

# 4. Force re-testing on an already published page
python jobs/pinterest-publisher/main.py --dry-run --force --doc-id <FIRESTORE_DOC_ID>

# 5. Run live execution (Publishes Pin live to Pinterest via Buffer)
python jobs/pinterest-publisher/main.py
```

Or use the root Makefile shortcuts:
```bash
make pinterest-test    # Runs local dry-run
make pinterest-deploy  # Deploys to Cloud Run Functions
```

---

## 🏃 Deployment

Deploy the Cloud Run Function using `deploy.sh`:

```bash
cd jobs/pinterest-publisher
./deploy.sh
```
