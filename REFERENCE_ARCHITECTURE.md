# Project: Color It Daily Agent Architecture

**Framework:** Google ADK (Agent Development Kit)

## Project Context & Mission

**Color It Daily** is a website dedicated to providing high-quality, printable coloring pages.

* **Promise**: Beautiful, optimized coloring pages available always for free.
* **Cadence**: A brand new, unique page is generated, vetted, and added to the collection every single day.
* **Primary Audience (Current):** Children (Ages 3–10). Content must be simple, engaging, and easy to color.
* **Secondary Audience (Future Goal):** Adults/General. More complex styles (Mandalas, Scenery) will be introduced later.
* **Safety Mandate:** Regardless of the target audience complexity, **100% of content must be strictly child-safe (G-Rated).**

---

## High-Level Flow

The system is designed as a **Sequential Agent** (The Publisher) that orchestrates two primary components:

1. **The Editorial Team:** Determines *what* to create based on history, trends, and **child-appropriate themes**.
2. **The Studio Loop:** Generates, refines, and reviews the asset until it meets quality standards suitable for print.

---

## 1. Agent Architecture Breakdown

### A. The Publisher (Top-Level Orchestrator)

* **ADK Type:** `SequentialAgent`
* **Role:** Manages the handoff between Ideation and Production.
* **Logic:** Executes `ConceptAgent`  passes context  executes `StudioLoop`.

### B. Agent 1: The Creative Director (The "Fun" Filter)

* **ADK Type:** `LlmAgent`
* **Role:** Brainstorms unique concepts that fit the season and appeal to children.
* **Input:** Current date, access to history database.
* **Directives:**
* Prioritize whimsical, animals, fantasy, and simple seasonal themes.
* *Future Capability:* Can toggle "complexity_level" for adult audiences, but defaults to "kids".

* **Tools:**
* `search_past_concepts(query_embedding)`: Connects to PostgreSQL. Uses `pgvector` to find semantically similar past pages to avoid duplicates.
* `get_calendar_events()`: Returns current season, nearby holidays, and "National Day of..." data.

* **Output:** `ConceptJSON`
```json
{
  "title": "Winter Fox in Scarf",
  "description": "A cute fox sitting in snow wearing a knitted scarf.",
  "visual_tags": ["fox", "winter", "snow", "scarf", "nature"],
  "target_audience": "child",
  "complexity": "low",
  "mood": "Whimsical",
  "avoid_elements": ["complex background", "shading", "scary features"]
}

```

### C. The Studio Loop (Production Team)

* **ADK Type:** `LoopAgent`
* **Role:** Iterates on the image generation until quality standards are met.
* **Max Iterations:** 3 (to prevent infinite costs).
* **Loop Condition:** Continues while `CriticStatus == "REJECT"`.

#### Sub-Agent C1: The Stylist (Prompt Engineer)

* **ADK Type:** `LlmAgent`
* **Role:** Translates the `ConceptJSON` into a technical prompt optimized for "Nano Banana Pro."
* **Input:** `ConceptJSON` + (Optional) `CritiqueFeedback` from previous failed attempt.
* **Logic:**
* Selects a specific style collection based on `target_audience`.
* *If Kid:* Uses "Thick Line Chibi", "Bold Cartoon", "Simple Sticker".
* *If Adult (Future):* Uses "Intricate Mandala", "Fine Line Realism".


* **Output:** `positive_prompt`, `negative_prompt`.

#### Sub-Agent C2: The Critic (Quality & Safety Assurance)

* **ADK Type:** `LlmAgent` (Multimodal)
* **Role:** "Visually" inspects the final output for printability and safety.
* **Input:** The optimized image file + Original Description.
* **System Instruction:** "You are a strict art critic for **children's coloring pages**.
1. **Safety Check (Zero Tolerance):** Reject if content is scary, suggestive, or ambiguous.
2. **Quality Check:** Reject if lines are broken/faint or image contains grayscale shading (must be pure black/white).
3. **Complexity Check:** If `target_audience='child'`, reject if the image is too cluttered or has tiny details impossible to color with crayons."


* **Output:** `Status` (PASS/REJECT), `Feedback`.

---

## 2. Tooling Implementation Strategy

### Database & History (PostgreSQL)

* **Vector Search:** Do not rely on keyword tags. Implement `pgvector`.
* **Mechanism:** When the Creative Director proposes "Snowman," the tool converts "Snowman" to an embedding, queries the DB, and if high cosine similarity (>0.85) is found in the last 30 days, the Agent knows to pick a different topic.

### Image Processing Pipeline (Python Tools)

These should be wrapped as ADK `FunctionTools`.

1. **Generation Tool:**
* Wraps the **Nano Banana Pro** API.
* Returns a temporary file path.


2. **Optimization Tool (The "Darkroom"):**
* **Upscaling:** Use **Real-ESRGAN** (specifically `realesrgan-x4plus-anime`). This model is critical for keeping black lines sharp and not blurry.
* **Sizing:** Resize/Crop to **3300px x 2550px** (Landscape) or **2550px x 3300px** (Portrait).
* **Color Profile:** Convert to Grayscale or CMYK to ensure "Rich Black" doesn't ruin home printing.

---

## 3. The Execution Flow

1. **Trigger:** Daily scheduled job.
2. **Creative Director:** Checks date (Dec 20th) -> Checks History -> Proposes "Reindeer playing hockey." (Target: Child).
3. **Studio Loop (Attempt 1):**
* **Stylist:** Writes prompt: "thick line art, cute reindeer, hockey stick, ice rink, minimal background, coloring page style."
* **Generator:** Creates Image A.
* **Optimizer:** Upscales Image A.
* **Critic:** Reviews Image A. *Result: REJECT. Feedback: "The hockey stick merges with the leg. Lines are too thin for crayon use."*

4. **Studio Loop (Attempt 2):**
* **Stylist:** Receives feedback. Rewrites prompt: "thick bold lines, separated limbs, distinct hockey stick, simple outlines..."
* **Generator:** Creates Image B.
* **Optimizer:** Upscales Image B.
* **Critic:** Reviews Image B. *Result: PASS.*


5. **Publisher:** Saves Image B to GCS bucket, updates History (database), setup featured image, invalidate website cache (Next.js)

---

## 4. Key Recommendations for Improvement

* **Feedback Injection:** Ensure the `LoopAgent` passes the Critic's text feedback *back* into the Stylist's context window for the next turn. Without this, the Stylist is guessing blindly on the retry.
* **Style Consistency & Difficulty Mapping:**
* Map styles not just to Moods, but to **Difficulty Levels**:
* *Level 1 (Kids/Current):* Thick Line Cartoon, Simple Shapes.
* *Level 2 (Older Kids):* Scene with Background.
* *Level 3 (Adult/Future):* Mandala/Geometric, Fine Detail.