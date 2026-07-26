# Color It Daily Agent 🎨

> An autonomous AI editorial team that conceptualizes, illustrates, critiques, and publishes high-quality children's coloring pages every single day.

**Color It Daily** is a fully automated content pipeline designed to deliver fresh, child-safe, and print-optimized coloring pages. The system uses a multi-agent architecture to mimic a real-world creative studio, ensuring variety, safety, and technical excellence without human intervention.

---

## 🌟 Core Features

* **Autonomous Creativity:** The "Creative Director" conceptualizes fresh daily topics, using rich ideation engines (whimsical mashups, micro-worlds, magical architecture, sweet discoveries) to avoid generic tropes.
* **Dynamic Collection & Creative Skills:** Supports targeted collections (e.g. `Wonder Daily`, `A Pirate's Life`, `Halloween`). Automatically pulls and validates the collection's `creative_skill`, `heading`, and `description` style, transforming agent prompts dynamically.
* **Studio Quality Loop:** A feedback loop between the "Stylist" (Prompt Engineer) and "Critic" (Multimodal QA Agent) ensures every image adheres to the collection's target artistic style and strict **No Text** mandate.
* **Pre-Agent Document Persistence:** Pre-creates a document record (`status: "running"`) in Firestore (or local JSON) with a unique document ID before calling the agent.
* **Firestore Input Overrides:** Automatically checks Firestore collection `coloritdaily_config/agent_input` to dynamically override POST request inputs without needing extra GCS buckets.
* **No-Persistence Local Mode (`no_persist: true`)**: Local testing mode that skips Cloud Storage and Firestore, saving raw assets, vector outputs, and the document record (`document.json`) to a local directory for review.
* **Print-Ready Optimization:** Automatically converts AI-generated raster images into crisp, scalable Vectors (SVG) using `potrace`, ensuring 100% black-and-white lines with no gray shading.
* **Strict Safety & No Text Mandate:** A zero-tolerance policy enforced by the Critic agent prevents scary/suggestive content and rejects any written text, letters, or typography.

---

## 🏗️ Architecture

The system is built on the **Google Agent Development Kit (ADK)** and follows a sequential multi-agent workflow:

### 1. Request Interception & Pipeline (`main.py` / `pipeline.py`)
* Merges payload with Firestore document `coloritdaily_config/agent_input` overrides.
* Validates `collection_name` in Firestore `coloritdaily_collections` (falls back to `"Wonder Daily"`).
* Pre-creates document in Firestore (`status: "running"`).
* Sets thread/async-safe `AgentContext`.

### 2. The Creative Director (Strategy)
* Brainstorms the daily concept matching the target `creative_skill` and collection `description`.
* Rotates themes and visual arrangements.

### 3. The Studio Loop (Production & Quality Control)
* **The Stylist:** Converts the concept into a rich, natural-language text prompt describing the subject, framing, and `creative_skill` style.
* **The Generator:** Calls the image generation model and runs the **Vectorization Pipeline** (`potrace`) to create a high-res SVG.
* **The Critic:** A multimodal vision agent that inspects the final image for:
  * Child safety & Zero Tolerance for written text/words.
  * Zero-tolerance border/frame elimination.
  * Print-ready line clarity (no shading/grayscale).
  * **Creative Skill Compliance** matching the target collection style.
  * Calls `publish_to_firestore` upon approval.

---

## 🎨 Collection Schema & Prompt Starter Guide

When creating a new collection in Firestore (`coloritdaily_collections`), populate the following fields so both your frontend UI and the AI agent have full context:

### Collection Fields & Purpose

| Field | Type | Purpose & Target |
| :--- | :--- | :--- |
| `name` | `string` | Display name of the collection (e.g., `"Kawaii Kingdom"`). |
| `slug` | `string` | URL slug & document lookup ID (e.g., `"kawaii-kingdom"`). |
| `heading` | `string` | **Frontend UI**: Catchy marketing headline displayed on the website/app. |
| `description` | `string` | **Frontend UI**: Customer-facing summary describing the collection for users. |
| `context` | `string` | **Agent Vision**: Unifying storybook theme passed to `AgentContext` (`collection_context`). Directs the Creative Director, Stylist, and Critic on what all generations in this collection must have in common. |
| `creative_skill` | `string` | **Style & Composition Guide**: Detailed prompt instructions defining **Art Style & Line Technique**, **Composition & Framing**, and **Thematic Motifs**. |

---

### 📝 Prompt Starter to Generate a New Collection

Copy and paste the template below into an LLM whenever you want to generate a new collection document for **Color It Daily**:

```text
Act as a Creative Publisher for "Color It Daily," a premium children's coloring page app.
I want to create a brand new collection centered around the topic: "[INSERT YOUR TOPIC HERE, e.g. Magical Dinosaurs]".

Please generate a JSON object with the following fields:

1. "name": A catchy display name for the collection.
2. "slug": A URL-friendly slug version of the name.
3. "heading": A high-impact marketing headline for our frontend UI.
4. "description": A short, engaging 1-2 sentence summary for users browsing our frontend app.
5. "context": A detailed 2-3 sentence storybook vision explaining what ALL coloring pages generated for this collection must have in common (e.g. specific mood, setting, character dynamics, and child-safe tone).
6. "creative_skill": A comprehensive artistic style guide covering:
   - Art Style & Line Technique (e.g., line thickness, vector closed shapes, zero shading)
   - Composition & Framing (e.g., focal points, background complexity, coloring region size for ages 3-10)
   - Thematic Motifs (e.g., specific subjects, objects, and visual elements to include)

Output ONLY valid JSON.
```

---

## 🚀 Installation & Setup

### Prerequisites
* **Python 3.10+**
* **Google Cloud Platform Project** with Vertex AI, Cloud Storage (GCS), and Firestore enabled.
* **System Dependency:** `potrace` (required for SVG vectorization).

```bash
# Linux (Debian/Ubuntu)
sudo apt-get update && sudo apt-get install -y potrace

# macOS
brew install potrace
```

### Python Environment Setup

```bash
git clone https://github.com/your-repo/color-it-daily-agent.git
cd color-it-daily-agent
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 🧪 Local Testing & Usage

### Option 1: Automated Unit & Integration Test Suite
Run local unit tests covering collection validation, pre-creation of documents, dynamic instructions, and `no_persist` local mode:

```bash
venv/bin/python /home/ostamand/.gemini/antigravity-cli/brain/2f9a3a54-8004-4b2d-b90b-5f2bf13e3763/scratch/test_agent_controls.py
```

---

### Option 2: Run FastAPI Server Locally & Trigger API Calls

#### Step 1: Start the Local Server with Hot Reload
```bash
make dev
# (or: uvicorn main:app --host 0.0.0.0 --port 8080 --reload)
```

#### Step 2: Trigger Agent Runs via `call-agent.py`

* **Default Run (Collection: "Wonder Daily")**:
  ```bash
  python call-agent.py --endpoint http://localhost:8080
  ```

* **Run with Specific Collection**:
  ```bash
  python call-agent.py --endpoint http://localhost:8080 --collection "Wonder Daily"
  ```

* **Run in Local No-Persistence Mode (`--no-persist`)**:
  ```bash
  python call-agent.py --endpoint http://localhost:8080 --collection "Wonder Daily" --no-persist
  ```
  *(Saves raw image, optimized PNG/SVG, and local `document.json` under `./tmp/color_it_daily/<document_id>/` without writing to GCS or Firestore).*

---

### Option 3: Test Firestore Input Overrides

1. Set fields in your Firestore document `coloritdaily_config/agent_input`:
   ```json
   {
     "collection_name": "Wonder Daily",
     "no_persist": true
   }
   ```
2. Make an API call via `call-agent.py`:
   ```bash
   python call-agent.py --endpoint http://localhost:8080
   ```
3. The server middleware automatically fetches document `coloritdaily_config/agent_input` from Firestore, merges non-null fields over the request payload, and executes the agent accordingly!

---

## 🛠️ Project Structure

* `main.py` - FastAPI app entrypoint with middleware request interception.
* `call-agent.py` - CLI test trigger tool supporting `--collection` and `--no-persist`.
* `deploy.sh` - Bash deployment script reading credentials from `.env`.
* `seed_collections.py` - Seeding tool mapping PostgreSQL collections to Firestore `coloritdaily_collections`.
* `color_it_daily_agent/` - Package root.
  * `context.py` - Thread/async-safe `AgentContext` holder.
  * `pipeline.py` - Pre-agent initialization (Firestore config merge, collection check, doc pre-creation).
  * `lib/collections.py` - Collection, `description` & `creative_skill` lookup and validation.
  * `lib/firestore_config.py` - Firestore configuration override loader (`coloritdaily_config/agent_input`).
  * `lib/persistence.py` - Document pre-creation and update logic (Firestore & local JSON).
  * `creative_director/` - Strategy agent & rich ideation instructions.
  * `stylist/` - Dynamic prompt engineering agent.
  * `generator/` - Image generation and `potrace` optimization tools.
  * `critic/` - Multimodal QA agent and Firestore publisher.

---

## 📄 License
[MIT License](LICENSE)