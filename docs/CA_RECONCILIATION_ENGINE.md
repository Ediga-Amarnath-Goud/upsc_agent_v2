# Precision Current Affairs & Reconciliation Engine

This is the comprehensive, production-ready architectural plan to develop your **Precision Current Affairs & Reconciliation Engine**. This plan integrates directly with the engineering paradigms defined in your existing **SYSTEM_ARCHITECTURE.md** file.

It is optimized for a single-user architecture, operating strictly within free-tier API boundaries, and engineered specifically around a curated "Editors' Cut" model to eliminate the 200-article noise swamp while ensuring landmark legal updates (like the "Right to Walk") are never dropped.

---

## Core Architectural Blueprint

```
                      [ 6 Whitelisted RSS Feeds ]
                                  |
                                  ▼ (6:00 AM IST)
                  [ 2-Pass Precision Gatekeeper ]
                   ├── Pass 1: Heuristic Override (VIP Lane)
                   └── Pass 2: Chunk-Based Vector Match
                                  |
                       Passed? ───┴─── No ───> [ Silently Drop ]
                         |
                         ▼ Yes
            [ gemini-3.1-flash-lite Schema Parse ]
                         |
                         ▼
             [ data/current_affairs.db Hub ] <─── [ TrendMetrics Cache ]
                         ▲                               ▲
                         |                               |
        [ POST /current-affairs/upload-pdf ] ────────────┘
         (LlamaParse Academy Material Ingest)
                         |
                         ▼
        [ gemini-3-flash-preview Trap Analysis ] ──> [ Daily EOD PDF Digest ]
```

---

## 1. Storage & Schema Definition Layer

To support the threaded analytical data streams, we expand the schemas without introducing multi-tenant complexity. All data configurations target `data/current_affairs.db` as defined in your **SYSTEM_ARCHITECTURE.md**.

### SQLAlchemy ORM Models (`backend/models.py` Extensions)

Since SQLite does not natively parse complex Python lists, text-serialized JSON fields are implemented.

```python
# Extension for backend/models.py
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Float
from datetime import datetime
from backend.database import Base

class CurrentAffairs(Base):
    __tablename__ = 'current_affairs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    issue_id = Column(String, index=True, nullable=False) # Maps 48h rolling threads
    title = Column(String, nullable=False)
    source_url = Column(String, unique=True, nullable=False)
    full_text = Column(Text, nullable=False)
    summary = Column(Text, nullable=False)
    gs_linkage = Column(String, nullable=False)           # Subject taxonomy string
    
    # Text-Serialized JSON objects (Lists/Dicts)
    supporting_arguments = Column(Text, nullable=False)    # JSON representation of List[str]
    counter_arguments = Column(Text, nullable=False)       # JSON representation of List[str]
    way_forward = Column(Text, nullable=False)             # JSON representation of List[str]
    prelims_high_yield_facts = Column(Text, nullable=False)# JSON representation of List[str]
    predicted_traps = Column(Text, nullable=True)          # JSON representation of TrapForecastSchema dict
    
    # Reconciliation Audit Flags
    matched_via = Column(String, nullable=False)           # 'Heuristic VIP' or 'Chunk-Vector'
    is_academy_verified = Column(Boolean, default=False)
    is_supplemental = Column(Boolean, default=False)
    date_fetched = Column(DateTime, default=datetime.utcnow)

class TrendMetrics(Base):
    __tablename__ = 'trend_metrics'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    topic_tag = Column(String, unique=True, index=True, nullable=False)
    live_feed_frequency = Column(Integer, default=0)
    academy_pdf_frequency = Column(Integer, default=0)
    computed_density_score = Column(Float, default=0.0)
    last_calibrated = Column(DateTime, default=datetime.utcnow)
```

### Pydantic Data Structures (`backend/schemas.py` Extensions)

These handle strict application-layer data formatting before interacting with your React components.

```python
# Extension for backend/schemas.py
from pydantic import BaseModel, Field
from typing import List, Optional

class TrapForecastSchema(BaseModel):
    trap_type: str = Field(description="Taxonomy class, e.g., Extreme Quantifiers, Institutional Swapping")
    mechanism: str = Field(description="How a question-setter would manipulate this news fact to trick a student")
    elimination_clue: str = Field(description="The logical anchor used to dismantle the trap during testing")

class FinalizedCAEntrySchema(BaseModel):
    issue_id: str
    core_issue: str
    gs_linkage: str
    supporting_arguments: List[str]
    counter_arguments: List[str]
    way_forward: List[str]
    prelims_high_yield_facts: List[str]
    predicted_traps: Optional[TrapForecastSchema] = None
    matched_via: str
    is_academy_verified: bool = False
    is_supplemental: bool = False
```

---

## 2. The Intake Spoke: 2-Pass Precision Gatekeeper

This logic replaces the standard text extraction routines within your `current_affairs.py` pipeline. It isolates the structural legal anchors from surrounding conversational noise before interacting with cloud tokens.

```python
# Module integrated within backend/current_affairs.py
import re
from sentence_transformers import SentenceTransformer, util

embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

# VIP overrides for high-yield legal parameters
LANDMARK_HEURISTICS = [
    (r"fundamental right", r"article (14|19|21|32|226)"),
    (r"supreme court", r"(landmark judgment|constitutional bench|struck down|quashed|held that)"),
    (r"high court", r"(issued writ|mandamus|quashed|directed the state)"),
    (r"amendment", r"constitutional \(\d+th\s+amendment\)")
]

def evaluate_precision_intake(article_text: str, title: str, syllabus_vectors, atomic_syllabus_list) -> dict:
    """
    Executes a high-precision two-pass evaluation to catch key legal updates
    while filtering out standard administrative bloat.
    """
    combined_clean = f"{title.lower()} {article_text.lower()}"
    
    # === PASS 1: THE HEURISTIC VIP LANE ===
    for pattern_a, pattern_b in LANDMARK_HEURISTICS:
        if re.search(pattern_a, combined_clean) and re.search(pattern_b, combined_clean):
            return {
                "passed": True,
                "score": 1.0,
                "matched_via": "Heuristic Override (Constitutional/Judicial Landmark)",
                "matched_micro_topic": "Polity & Governance - Constitutional Edict"
            }

    # === PASS 2: CHUNK-BASED VECTOR MATCHING ===
    # Break the article into 3-paragraph chunks to isolate semantic dilution
    paragraphs = [p.strip() for p in article_text.split("\n\n") if p.strip()]
    chunks = ["\n\n".join(paragraphs[i:i+3]) for i in range(0, len(paragraphs), 2)]
    
    max_vector_score = 0.0
    best_matched_topic = None
    
    for chunk in chunks:
        chunk_vector = embedding_model.encode(chunk, convert_to_tensor=True)
        cosine_scores = util.cos_sim(chunk_vector, syllabus_vectors)[0]
        current_max_idx = cosine_scores.argmax().item()
        current_max_score = cosine_scores[current_max_idx].item()
        
        if current_max_score > max_vector_score:
            max_vector_score = current_max_score
            best_matched_topic = atomic_syllabus_list[current_max_idx]

    # Calculate and apply Political Noise penalties to Pass 2
    noise_signifiers = ["election rally", "vote bank", "opposition slammed", "poll promises", "seat sharing"]
    noise_count = sum(combined_clean.count(word) for word in noise_signifiers)
    if noise_count > 2:
        max_vector_score *= 0.75  # 25% mathematical deduction for political news

    # Tight operational gatekeeper threshold
    if max_vector_score >= 0.65:
        return {
            "passed": True,
            "score": round(max_vector_score, 3),
            "matched_via": "Chunk-Vector Match",
            "matched_micro_topic": best_matched_topic
        }
        
    return {
        "passed": False,
        "reason": f"Failed both Heuristic and Chunk-Vector checks ({round(max_vector_score, 3)})",
        "score": round(max_vector_score, 3)
    }
```

---

## 3. The Two-Way Reconciliation & Trend Analytics Spoke

This system forces your whitelisted live data pool and your incoming academy PDFs to cross-audit each other.

### Mathematical Consistency Engine

When a document chunk is evaluated against the `CurrentAffairs` space, it verifies semantic affinity via the cosine similarity formula:

$$\text{Similarity}(\mathbf{A}, \mathbf{B}) = \frac{\mathbf{A} \cdot \mathbf{B}}{\|\mathbf{A}\| \|\mathbf{B}\|}$$

- **Intersection ($\ge 0.82$):** Flags the record as `is_academy_verified = True`.
- **The Missing Link ($< 0.82$):** The system routes the academy chunk to `gemini-3.1-flash-lite` to extract core data with `is_supplemental = True`.

### Pre-Calculated Caching Pipeline

To maintain low execution times on a local SQLite infrastructure, do not run matrix comparisons on the fly. Instead, use the following operational lifecycle script within `POST /current-affairs/upload-pdf`:

```python
# Module integrated within backend/current_affairs.py
def update_trend_metrics_cache(db_ca_session, topic_tag: str, increment_source: str):
    """
    Maintains a local cache table to store trend weights, preventing
    performance drops on local database queries.
    """
    metric = db_ca_session.query(TrendMetrics).filter(TrendMetrics.topic_tag == topic_tag).first()
    if not metric:
        metric = TrendMetrics(topic_tag=topic_tag)
        db_ca_session.add(metric)
        
    if increment_source == "live_feed":
        metric.live_feed_frequency += 1
    elif increment_source == "academy_pdf":
        metric.academy_pdf_frequency += 1
        
    # Calculate the composite trend weight
    metric.computed_density_score = (metric.live_feed_frequency * 0.4) + (metric.academy_pdf_frequency * 0.6)
    metric.last_calibrated = datetime.utcnow()
    db_ca_session.commit()
```

---

## 4. ELO-Driven CA Trap Forecasting Engine

This module connects incoming news trends to your historical learning data, implementing the dynamic trap targeting outlined in your **SYSTEM_ARCHITECTURE.md**.

```python
# backend/ca_trap_analyzer.py
import json
from backend.models import StudentProfile, CurrentAffairs
from backend.model_config import get_model_client # Aligns with system client wrappers

def inject_personalized_trap_predictions(db_main, db_ca, current_article_id: int):
    """
    Cross-references single-student trap records to pre-compute custom exam alerts.
    """
    # Pull profile status from main DB
    student = db_main.query(StudentProfile).filter(StudentProfile.student_id == "default").first()
    article = db_ca.query(CurrentAffairs).filter(CurrentAffairs.id == current_article_id).first()
    
    # Read weakest trap pattern based on accuracy tracking (from math_utils.py)
    # Target model: ca_analysis layer (gemini-3-flash-preview) via system architecture mapping
    weakest_trap = "Institutional Swapping" 
    
    prompt = f"""
    You are an adversarial UPSC Question Setter. 
    Analyze this analytical issue context:
    Core Issue: {article.title}
    Taxonomy: {article.gs_linkage}
    High-Yield Facts: {article.prelims_high_yield_facts}
    
    The student is highly vulnerable to '{weakest_trap}' traps.
    Generate a valid JSON object matching TrapForecastSchema that builds a question trap 
    manipulating the high-yield facts of this specific news item to exploit that vulnerability.
    """
    
    # Complete execution via the abundant tier client layer
    # Response is serialized directly into article.predicted_traps
```

---

## 5. Execution Cadence & Routing Matrix

### 1. The 6:00 AM Automated Background Task

The system startup routine configures a single-run trigger that runs early in the morning. It targets whitelisted URLs (PIB, PRS, *The Hindu Editorials*, *Indian Express Explained*). It drops political chatter at zero token cost and uses the `ca_parser` model (`gemini-3.1-flash-lite`) to populate your local database.

### 2. Manual Verification Route Updates

The existing manual fetch route is updated to prevent unfiltered data imports:

- `POST /api/current-affairs/fetch` is modified to process incoming text data through the **2-Pass Precision Gatekeeper** before committing any writes to your local SQLite database.

### 3. PDF Exporter Updates (`backend/pdf_generator.py`)

Your `fpdf` digest engine uses three structured blocks to layout your daily printouts:

- **Section 1: Curated Analysis:** Displays structural editorial summaries alongside balanced argument tables.
- **Section 2: UPSC Trap Alert Containers:** Renders high-visibility boxes highlighted with border paths to show the `trap_type`, `mechanism`, and `elimination_clue` strings.
- **Section 3: Academy Supplement Annex:** Appends a distinct appendix section showing any items where `is_supplemental == True`, providing perfect syllabus coverage.

---

## Development Checklist

- [ ] **Phase 1: DB Realignment:** Add the JSON column models and the tracking fields to your local database files.
- [ ] **Phase 2: Core Gatekeeper Hook:** Replace the standard text processing loop with the heuristic bypass and the chunked vector scoring block within your main script pipeline.
- [ ] **Phase 3: Reconciliation Engine Wire:** Update the PDF file upload endpoints to route text streams through LlamaParse and populate your trend analytics cache tables.
- [ ] **Phase 4: Adaptive Generation Patch:** Connect the script prompts to your local user tracking profile records and update your PDF document generation templates.
