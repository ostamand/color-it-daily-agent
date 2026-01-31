# Color It Daily Agent 🎨

> An autonomous AI editorial team that conceptualizes, illustrates, critiques, and publishes high-quality children's coloring pages every single day.

**Color It Daily** is a fully automated content pipeline designed to deliver fresh, G-rated, and print-optimized coloring pages. The system uses a multi-agent architecture to mimic a real-world creative studio, ensuring variety, safety, and technical excellence without human intervention.

## 🌟 Core Features

*   **Autonomous Creativity:** The "Creative Director" agent plans content based on seasons, holidays, and past history to ensure variety (e.g., no two "animal" pages in a row).
*   **Studio Quality:** A feedback loop between a "Stylist" (Prompt Engineer) and a "Critic" (QA Vision Agent) ensures every image is printable, simple, and error-free.
*   **Print-Ready Optimization:** Automatically converts AI-generated raster images into crisp, scalable Vectors (SVG) using `potrace`, ensuring 100% black-and-white lines with no gray shading.
*   **Strict Safety:** A zero-tolerance "G-Rating" policy enforced by the Critic agent prevents scary, suggestive, or ambiguous content.
*   **Composition Variety:** Rotates between styles like **Character Stickers**, **Full Scenes**, and **Mandalas**.

---

## 🏗️ Architecture

The system is built on the **Google Agent Development Kit (ADK)** and follows a sequential multi-agent workflow:

### 1. The Publisher (Orchestrator)
The top-level agent that manages the entire workflow, handing off tasks from ideation to production.

### 2. The Creative Director (Strategy)
*   **Role:** Brainstorms the daily concept.
*   **Logic:** Checks the calendar (holidays/seasons) and recent history to pick a fresh topic.
*   **Output:** A structured concept (e.g., "A Spring Flower Mandala").

### 3. The Studio Loop (Production)
A collaborative loop that iterates until the image is perfect (max 3 tries).

*   **The Stylist:** Converts the concept into a highly technical image prompt, selecting specific "micro-styles" (e.g., "Bold Sticker" or "Whimsical Storybook").
*   **The Generator:** Calls the image generation model (Nano Banana Pro) and runs the **Vectorization Pipeline** (Potrace) to create a high-res SVG.
*   **The Critic:** A multimodal agent that "looks" at the result. It rejects images with:
    *   Broken lines or gray shading.
    *   Scary or unsafe elements.
    *   **Borders** (Strict borderless requirement).
    *   Composition errors (e.g., items touching in a "Collection").

---

## 🚀 Installation & Setup

### Prerequisites
*   **Python 3.10+**
*   **Google Cloud Platform Project** with:
    *   Vertex AI API enabled.
    *   Cloud Storage (GCS) enabled.
    *   Firestore enabled.

### 1. System Dependencies
This project relies on `potrace` for vectorization. You **must** install this system-level dependency.

**Linux (Debian/Ubuntu/Cloud Run):**
```bash
sudo apt-get update && sudo apt-get install -y potrace
```

**macOS:**
```bash
brew install potrace
```

### 2. Python Environment
Clone the repository and install dependencies:

```bash
git clone https://github.com/your-repo/color-it-daily-agent.git
cd color-it-daily-agent
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configuration
Create a `.env` file in the root directory with your GCP details:

```env
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GCS_MEDIA_BUCKET=your-media-bucket-name
# Firestore Collection for saving metadata
FIRESTORE_COLLECTION=coloring_pages
```

---

## 🏃‍♂️ Usage

### Run the Agent Manually
To trigger a single run of the daily generation process:

```bash
python -m color_it_daily_agent.agent
```

### Project Structure

*   `color_it_daily_agent/` - Main package.
    *   `creative_director/` - Strategy agent logic and tools.
    *   `stylist/` - Prompt engineering agent.
    *   `generator/` - Image generation and `potrace` optimization tools.
    *   `critic/` - Vision-based QA agent.
*   `jobs/` - Cloud Run jobs for scheduling.
    *   `daily-push/` - The main scheduled task.
    *   `generate-thumbnail/` - Helper job for UI assets.

---

## 🛠️ Development

### Adding a New Style
1.  Open `color_it_daily_agent/creative_director/instructions.py`.
2.  Add a new **Composition Type** (e.g., "Type E: The 'Educational Map'").
3.  Open `color_it_daily_agent/stylist/instructions.py`.
4.  Add a corresponding **Micro-Style** prompt strategy.

### Adjusting Safety Rules
Modify `color_it_daily_agent/critic/instructions.py` to add new rejection criteria (e.g., "Reject images with text").

---

## 📄 License
[MIT License](LICENSE)