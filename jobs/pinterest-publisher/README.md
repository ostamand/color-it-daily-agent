# 📌 Pinterest Publisher Service (`pinterest-publisher`)

A standalone Cloud Run Function microservice that automatically fetches published coloring pages from Firestore, sorts by latest, and posts them to Pinterest using **Gemini 3.5 Flash** for copywriting and **Pinterest API v5**.

---

## 🌟 Features

* **Latest-First Sorting**: Automatically selects the most recent published coloring page on `coloritdaily.com` that has not yet been pinned to Pinterest.
* **Gemini 3.5 Flash Copywriting**: Crafts high-converting Pin titles, parent/teacher-oriented descriptions, and targeted hashtags.
* **Smart Multi-Board Routing**: Uses `PINTEREST_BOARD_MAP` to route pins to specialized boards (e.g. animals, mandalas, holidays) or falls back to `PINTEREST_BOARD_ID`.
* **Zero-Downtime Resilience**: Completely decoupled from image generation and website database publishing.
* **Dry-Run Mode**: Runs safely in dry-run mode when tokens are unconfigured.

---

## 🏃 Deployment

```bash
cd jobs/pinterest-publisher

export PINTEREST_ACCESS_TOKEN="pina_..."
export PINTEREST_BOARD_ID="123456789"
export PINTEREST_BOARD_MAP='{"animal": "1111", "mandala": "2222"}'
export SERVICE_ACCOUNT="color-it-daily-agent@ostamand-264a1.iam.gserviceaccount.com"

./deploy.sh
```

---

## 🧪 Local Testing & CLI Usage

You can test the script locally before deploying using `argparse` flags:

```bash
# 1. Run in dry-run mode (simulates Pinterest posting without calling external API)
python jobs/pinterest-publisher/main.py --dry-run

# 2. Test a specific Firestore Document ID in dry-run mode
python jobs/pinterest-publisher/main.py --dry-run --doc-id <FIRESTORE_DOC_ID>

# 3. Force re-testing on an already published page
python jobs/pinterest-publisher/main.py --dry-run --force --doc-id <FIRESTORE_DOC_ID>

# 4. Process up to 3 pending unpublished pages
python jobs/pinterest-publisher/main.py --dry-run --limit 3
```

