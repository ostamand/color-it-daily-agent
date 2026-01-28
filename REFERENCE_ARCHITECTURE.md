# Project: Color It Daily Agent Architecture

**Framework:** Google ADK (Agent Development Kit)

## Project Context & Mission

**Color It Daily** is a website dedicated to providing high-quality, printable coloring pages.

* **Promise:** Beautiful, optimized coloring pages available always for free.
* **Cadence:** A brand new, unique page is generated, vetted, and added to the collection every single day.
* **Primary Audience (Current):** Children (Ages 3–10). Content must be simple, engaging, and easy to color.
* **Secondary Audience (Future Goal):** Adults/General. More complex styles (Mandalas, Scenery) will be introduced later.
* **Safety Mandate:** Regardless of the target audience complexity, **100% of content must be strictly child-safe (G-Rated).**

---

## High-Level Flow

The system is designed as a **Sequential Agent** (The Publisher) that orchestrates two primary components:

1. **The Editorial Team (Creative Director):** Determines *what* to create using a rotation of subjects and composition strategies.
2. **The Studio Loop:** A feedback-driven loop where a **Stylist** and **Critic** iterate until the asset meets specific printability standards.

---

## 1. Agent Architecture Breakdown

### A. The Publisher (Top-Level Orchestrator)

* **ADK Type:** `SequentialAgent`
* **Role:** Manages the handoff between Ideation and Production.
* **Logic:** Executes `ConceptAgent`  passes context  executes `StudioLoop`.

### B. Agent 1: The Creative Director (The Strategist)

* **ADK Type:** `LlmAgent`
* **Role:** Brainstorms unique concepts by rotating both **Subject Categories** and **Composition Strategies** to ensure gallery variety.
* **Input:** JSON Payload `{"current_date": "YYYY-MM-DD"}`
* **Directives:**
   * **Analyze Context:** Check calendar for holidays/seasons.
   * **Rotate Category:** Switch between Animals, Fantasy, Jobs, Vehicles, Nature, Daily Life.
   * **Rotate Composition:** Switch between **Type A (Character Sticker)**, **Type B (Full Scene)**, **Type C (Collection)**, and **Type D (Action Shot)**.
   * **De-duplication:** Ensure no semantic overlap with past content.


* **Tools:**
    * `get_calendar_events(target_date_str)`: Returns season, holidays, and fun observances to ensure timeliness.
    * `get_recent_history(limit)`: Checks the last 3 published pages to enforce variety.
    * `search_past_concepts(concept_description)`: Vector search (Firestore) to find semantically identical past pages.


* **Output:** `ConceptJSON`

```json
{
  "title": "Space Explorer Kit",
  "description": "A collection of space items: a helmet, a rocket, a planet, and a star.",
  "visual_tags": ["space", "helmet", "collection", "pattern"],
  "target_audience": "child",
  "complexity": "low",
  "mood": "Fun",
  "avoid_elements": ["overlapping items", "tiny details"]
}

```

### C. The Studio Loop (Production Team)

* **ADK Type:** `LoopAgent`
* **Role:** Iterates on the image generation until quality standards are met.
* **Max Iterations:** 3 (to prevent infinite costs).
* **Loop Condition:** Continues while `CriticStatus == "REJECT"`.
* **Execution Chain:** `Stylist` -> `Generator` -> `Optimizer` -> `Critic`.

#### Sub-Agent C1: The Stylist (Prompt Engineer)

* **ADK Type:** `LlmAgent`
* **Role:** Transforms the `ConceptJSON` into a descriptive, natural language prompt strictly adhering to a technical **Micro-Style**.
* **Input:** `ConceptJSON` + (Optional) `CritiqueFeedback` from previous failed attempt.
* **Tools:** None.
* **Output:** JSON Payload
  ```json
  {
    "title": "...",
    "description": "...",
    "visual_tags": [...],
    "mood": "...",
    "target_audience": "...",
    "positive_prompt": "Detailed natural language description...",
    "negative_prompt": "Forbidden elements..."
  }
  ```

#### Sub-Agent C2: The Generator (Artist)

* **ADK Type:** `LlmAgent`
* **Role:** Adapts the prompt and executes the generation tool.
* **Input:** JSON Payload from Stylist (containing `positive_prompt` and `negative_prompt`).
* **Tools:**
    * `generate_image(positive_prompt, negative_prompt)`: Wraps **Nano Banana Pro** API. Returns a temporary file path.
* **Output:** JSON Payload
  ```json
  {
    "title": "...",
    "description": "...",
    "visual_tags": [...],
    "mood": "...",
    "target_audience": "...",
    "positive_prompt": "...",
    "negative_prompt": "...",
    "raw_image_path": "gs://..."
  }
  ```

#### Sub-Agent C3: The Optimizer (Darkroom Technician)

* **ADK Type:** `LlmAgent`
* **Role:** Processes the raw image for high-quality printing.
* **Input:** File Path from Generator.
* **Tools:**
    * `optimize_image(image_path)`: Wraps **Real-ESRGAN** (specifically `realesrgan-x4plus-anime`) and performs resizing/cropping to **3300px x 2550px**. Returns path to optimized image.
* **Output:** File Path (String) e.g., `"/tmp/optimized_image_123.png"`

#### Sub-Agent C4: The Critic (Quality & Safety Assurance)

* **ADK Type:** `LlmAgent` (Multimodal)
* **Role:** "Visually" inspects the final output for printability and safety.
* **Input:** The optimized image file path + Original Description (from context).
* **Tools:** None (Relies on Multimodal Vision Capabilities).
* **System Instruction:** "You are a strict art critic for **children's coloring pages**.
1. **Safety Check (Zero Tolerance):** Reject if content is scary, suggestive, or ambiguous.
2. **Quality Check:** Reject if lines are broken/faint or image contains grayscale shading.
3. **Composition Check:**
* If 'Sticker': Reject if background is cluttered.
* If 'Collection': Reject if items overlap or touch.

4. **Complexity Check:** Reject if details are too small for crayons."

* **Output:** JSON Payload
  ```json
  {
    "status": "PASS" | "REJECT",
    "feedback": "Reason for rejection or praise."
  }
  ```

---

## 2. Tooling Implementation Strategy

### Database & History (PostgreSQL)

* **Vector Search:** Do not rely on keyword tags. Implement `pgvector`.
* **Mechanism:** When the Creative Director proposes "Snowman," the tool converts "Snowman" to an embedding, queries the DB. If high cosine similarity (>0.85) is found in the last 30 days, the Agent must pivot to a different topic.

### Image Processing Pipeline (Python Tools)

These should be wrapped as ADK `FunctionTools`.

1. **Generation Tool:**
* Wraps the **Nano Banana Pro** API.
* Returns a temporary file path.

2. **Optimization Tool (The "Darkroom"):**
* **Upscaling:** Use **Real-ESRGAN** (specifically `realesrgan-x4plus-anime`). This model is critical for preserving sharp vector-like lines.
* **Sizing:** Resize/Crop to **3300px x 2550px** (Landscape) or **2550px x 3300px** (Portrait).
* **Color Profile:** Convert to Grayscale or CMYK to ensure "Rich Black" doesn't ruin home printing.

---

## 3. The Execution Flow

1. **Trigger:** Daily scheduled job.
2. **Creative Director:**
* Checks date (Dec 20th).
* History Check: Yesterday was "Scene/Nature".
* **Pivot:** Selects **Category: Daily Life** and **Composition: Collection**.
* Proposes: "Winter Clothing Kit" (Items: Mittens, Hat, Scarf, Boots).


3. **Studio Loop (Attempt 1):**
* **Stylist:** Detects tag "Collection". Selects **Micro-Style 5 (Icon Scatter)**.
   * *Prompt:* "A fun 'doodle sheet' coloring page... distinct items scattered evenly... no overlapping."
* **Generator:** Creates Image A.
* **Optimizer:** Upscales Image A.
* **Critic:** Reviews Image A.
   * *Result:* **REJECT**.
   * *Feedback:* "The scarf and the hat are touching in the center. Items must be isolated."

4. **Studio Loop (Attempt 2):**
* **Stylist:** Receives feedback. Rewrites prompt: "...ensure plenty of whitespace between the scarf and hat. Items must be completely separated..."
* **Generator:** Creates Image B.
* **Optimizer:** Upscales Image B.
* **Critic:** Reviews Image B.
   * *Result:* **PASS**.

5. **Publisher:** Saves Image B to GCS bucket, updates History (database), sets up featured image, invalidates website cache (Next.js).