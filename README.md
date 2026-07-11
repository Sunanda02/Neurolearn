# NeuroLearn — Adaptive Learning Platform

AI-powered e-learning platform with real-time attention monitoring, live video transcription, adaptive assessments, and gamification..

---

### Key Features

* Automated course generation from topic input
* Web scraping-based video discovery (no paid APIs)
* End-to-end pipeline: video → transcription → assessment
* AI transcription using Whisper
* NLP-based question generation (FLAN-T5)
* Adaptive assessment based on performance
* **Cognitive Readiness Score (CSR)** — multimodal fusion of performance, attention, response integrity, learning trend, and content complexity (see [CSR & MCL-DE](#cognitive-readiness-score-csr--mcl-de))
* Real-time attention tracking (MediaPipe)
* FastAPI backend with modular architecture
* Multi-source video support (YouTube, MP4, URLs)
* Deployment-ready full-stack system

## Demo Screens

### Dashboard
<p align="center">
  <img src="demo_files/dashboard.png" width="800">
</p>

### Video Learning
<p align="center">
  <img src="demo_files/video_learning.jpeg" width="800">
</p>

### Assessment
<p align="center">
  <img src="demo_files/assessment.png" width="800">
</p>

### Result
<p align="center">
  <img src="demo_files/result.png" width="800">
</p>

📄 **Assessment Report:** [View PDF](demo_files/NeuroLearn_Report_1772355573144.pdf)

```bash
cd neurolearn
npm install
npm run dev
# → Open http://localhost:3000
```

The frontend runs with **built-in dummy data** — no backend needed to explore the UI.

---

## Quick Start (Full Stack — Frontend + FastAPI Backend)

### Terminal 1: Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install fastapi uvicorn tinydb loguru python-dotenv
python main.py
# → API running at http://localhost:8000
# → Swagger docs at http://localhost:8000/docs
```

### Terminal 2: Frontend
```bash
npm install
npm run dev
# → Open http://localhost:3000
```

The frontend auto-detects whether the backend is running:
- **Backend UP** → uses real FastAPI endpoints + ML models
- **Backend DOWN** → falls back to local dummy data seamlessly

---

## Full ML Installation (Optional — for live AI features)

```bash
cd backend
pip install -r requirements.txt
```

This installs:
- **MediaPipe** → webcam attention detection (eye tracking, head pose, blink rate)
- **OpenAI Whisper** → live video transcription
- **FLAN-T5** → AI question generation from transcripts
- **PyTorch** → ML model runtime

Without these, the backend uses realistic **dummy data** in the exact same JSON format.

---

## Architecture

```
neurolearn/
├── app/                          # Next.js App Router pages
│   ├── page.tsx                  # Landing / splash redirect
│   ├── globals.css               # Dark theme + animations
│   ├── layout.tsx                # Root layout
│   ├── dashboard/                # Course grid + gamification
│   │   ├── layout.tsx
│   │   └── page.tsx
│   ├── video/                    # Video player + camera + AI panels
│   │   ├── layout.tsx
│   │   └── page.tsx
│   ├── assessment/               # Adaptive quiz
│   │   ├── layout.tsx
│   │   └── page.tsx
│   ├── results/                  # Score + adaptive feedback
│   │   ├── layout.tsx
│   │   └── page.tsx
│   ├── leaderboard/              # Global rankings
│   │   ├── layout.tsx
│   │   └── page.tsx
│   └── profile/                  # Student profile + badges
│       ├── layout.tsx
│       └── page.tsx
│
├── components/                   # Reusable UI components
│   ├── Sidebar.tsx               # Collapsible nav with XP/streak
│   ├── Navbar.tsx                # Top bar with search, notifs, profile
│   ├── TopicCard.tsx             # Course card with progress
│   ├── VideoPlayer.tsx           # MP4 + YouTube + any URL support
│   ├── CameraFeed.tsx            # Webcam → base64 frames → POST to API
│   ├── AttentionPanel.tsx        # Real-time attention score gauge
│   ├── TranscriptionPanel.tsx    # Live transcript synced to video
│   ├── VideoLinkSelector.tsx     # Course video picker
│   ├── AssessmentCard.tsx        # Quiz question with MCQ selection
│   ├── ResultCard.tsx            # Score display + adaptive feedback
│   ├── CSRPanel.tsx              # Cognitive Readiness gauge + 5-component breakdown (results page)
│   └── CSRTrendWidget.tsx        # CSR sparkline + current band (dashboard sidebar)
│
├── lib/
│   ├── api.ts                    # API layer (FastAPI → fallback → dummy)
│   ├── dummyDb.ts                # Local dummy data (all types + data)
│   └── utils.ts                  # cn() helper
│
├── backend/                      # FastAPI Python backend
│   ├── main.py                   # Entry point
│   ├── requirements.txt          # Python deps (merge-conflict fixed — see CHANGELOG below)
│   ├── config/
│   │   └── csr_config.py         # CSR weights, thresholds, all component sub-configs
│   ├── schemas/models.py         # Pydantic JSON models
│   ├── data/database.py          # TinyDB database (+ csr_history table)
│   ├── ml/
│   │   ├── attention_model.py    # MediaPipe face mesh → attention score (unchanged)
│   │   ├── transcription_model.py # Whisper → transcript segments (unchanged)
│   │   ├── question_generator.py # FLAN-T5 → quiz questions (unchanged)
│   │   ├── adaptive_engine.py    # CSR-driven difficulty selection (legacy rule cascade kept behind a config flag)
│   │   ├── csr.py                # Cognitive Readiness Score — fuses the 5 components below
│   │   ├── performance.py        # P — recency-weighted rolling average
│   │   ├── attention_subscores.py# A — sub-score views over attention_model (no duplication of fusion logic)
│   │   ├── response_integrity.py # I — timing-curve integrity, independent of correctness
│   │   ├── trend.py               # T — regression-slope learning trend
│   │   └── content_complexity.py # C — readability + technical-density transcript complexity
│   ├── routers/
│   │   ├── student.py            # Profile, XP
│   │   ├── courses.py            # Course listing, videos
│   │   ├── attention.py          # Camera frame → score
│   │   ├── transcription.py      # Video → transcript
│   │   ├── assessment.py         # Quiz generate + submit (now persists full CSR records)
│   │   ├── gamification.py       # Leaderboard, challenges
│   │   └── csr.py                # CSR + per-component history read endpoints
│   └── tests/
│       └── test_csr.py           # Unit tests for CSR and all 5 components (21 tests)
│
├── package.json
├── tsconfig.json
├── next.config.mjs
├── postcss.config.mjs
├── .env.local                    # NEXT_PUBLIC_API_URL
└── README.md
```

---

## Cognitive Readiness Score (CSR) & MCL-DE

NeuroLearn's adaptive difficulty selection is driven by the **Cognitive Readiness Score (CSR)**,
a weighted fusion of five components, computed fresh for every assessment:

```
CSR = α·P + β·A + γ·I + δ·T + ε·C        (all terms in [0,1]; α=β=γ=δ=ε=0.20 by default)
```

| Symbol | Component | What it measures | Module |
|---|---|---|---|
| **P** | Performance | Recency-weighted rolling average of recent assessment scores | `ml/performance.py` |
| **A** | Attention | Webcam-derived gaze / head-pose / blink-normality fusion (reuses `attention_model.py` unchanged) | `ml/attention_subscores.py` |
| **I** | Response Integrity | Triangular timing curve — penalizes both very-fast *and* very-slow responses, **independent of correctness** (a fast *correct* guess is still flagged) | `ml/response_integrity.py` |
| **T** | Learning Trend | Linear-regression slope over recent scores, saturated to [-1,1] and rescaled via `(T+1)/2` | `ml/trend.py` |
| **C** | Content Complexity | Flesch Reading Ease + technical-term density + sentence length, computed from the transcript the student actually watched | `ml/content_complexity.py` |

`ml/csr.py` fuses all five into one `CSRResult` (score, per-component breakdown, difficulty tier,
human-readable explanation). **MCL-DE** (the Multimodal Closed-Loop Difficulty Engine) is this
fusion plugged into `ml/adaptive_engine.py`: every assessment submission re-computes CSR from the
student's latest behavior and selects the next difficulty from configurable thresholds:

```
CSR > 0.75        → hard
0.45 ≤ CSR ≤ 0.75 → medium
CSR < 0.45        → easy
```

The loop closes because each submission's CSR (and its five components) is persisted to a
dedicated `csr_history` table and read back as `previous_scores`/trend input on the *next*
submission — see **Database Schema** and **API Endpoints** below.

### Configuration

Every weight, threshold, and window size lives in `backend/config/csr_config.py`
(`CSRWeights`, `DifficultyThresholds`, `PerformanceConfig`, `IntegrityConfig`, `TrendConfig`,
`ComplexityConfig`, `LegacyEngineConfig`) — nothing is hardcoded in the component modules.
`CSRConfig.csr_enabled` (default `True`) is a feature flag: setting it to `False` switches
`adaptive_engine.py` back to its original rule-cascade logic, preserved (not deleted) for A/B
comparison between the two engines.

### Database Schema — `csr_history` table

One TinyDB record per assessment submission:

```json
{
  "student_id": "student_001",
  "assessment_id": "session_1719... ",
  "timestamp": 1719999999.0,
  "performance": 0.82, "attention": 0.74, "integrity": 1.0,
  "trend": 0.61, "complexity": 0.55,
  "csr": 0.744, "difficulty": "medium",
  "explanation": "CSR = 0.20*P(0.82) + 0.20*A(0.74) + ... = 0.744 -> 'medium'. ..."
}
```

`get_recent_scores_pct()` reads the durable `results_table` (not an in-memory dict), so
Performance and Trend survive a server restart.

### Testing

```bash
cd backend
pip install -r requirements.txt   # merge-conflict markers removed — installs cleanly now
pytest tests/test_csr.py -v       # 21 tests: all 5 components + end-to-end CSR fusion
```

Notably includes a direct regression test for fast-but-*correct* answers being penalized by the
Integrity component — the scenario a pure accuracy-gated rule structurally cannot catch.

---

### Video Learning Session

```
Student opens /video?course=course_001

1. Frontend fetches course → GET /api/courses/course_001
2. Student plays video (MP4/YouTube/any URL)
3. Camera starts → captures frame every 3 seconds
4. Frame sent → POST /api/attention/snapshot
   Backend: MediaPipe Face Mesh → eye_contact, head_pose, blink_rate → score
   Returns: { score: 82, state: "attentive", model_response: {...} }
5. AttentionPanel updates in real-time
6. TranscriptionPanel polls → GET /api/transcription/{id}/live?current_time=15.3
   Backend: Whisper → text + word timestamps
   Returns: { text: "...", confidence: 0.94, model_response: {...} }
7. Video ends → "Take Assessment" button appears
```

### Assessment Flow

```
Student clicks "Take Assessment"

1. Navigate to /assessment?course=X&video=Y&attention=78
2. Frontend sends → POST /api/assessment/generate
   Body: { course_id, video_id, attention_score: 78, transcript_text: "..." }
   Backend: Adaptive Engine picks difficulty + FLAN-T5 generates questions
   Returns: { questions: [...], difficulty: "medium", adaptive_metadata: { reason } }
3. Student answers 5 questions (timer running)
4. Frontend sends → POST /api/assessment/submit
   Body: { session_id, answers: { q1: 1, q2: 0 }, time_spent: 180 }
   Backend: Grade → CSR/MCL-DE (Performance+Attention+Integrity+Trend+Complexity) → XP calculation
   Returns: {
     score: 80%, xp_earned: 120,
     adaptive_response: {
       performance_trend: "improving",
       next_assessment_difficulty: "hard",
       strength_areas: ["Core Concepts"],
       weak_areas: ["Applied Knowledge"],
       csr: {
         score: 0.78, score_pct: 78.0,
         components: { performance: 0.8, attention: 0.74, integrity: 1.0, trend: 0.61, complexity: 0.55 },
         explanation: "CSR = 0.20*P(0.80) + ... = 0.78 -> 'hard'. ..."
       }
     }
   }
5. Navigate to /results → shows score, XP, feedback, next steps, and the CSR gauge/breakdown
```

---
### Flowchart
<p align="center">
  <img src="/flow_diagram.png" width="800">
</p>

## API Endpoints Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/student/profile` | Student profile + badges |
| POST | `/api/student/xp` | Award XP (handles level-up) |
| GET | `/api/courses` | All courses with progress |
| GET | `/api/courses/{id}` | Course details + video links |
| GET | `/api/courses/{id}/videos/{vid}` | Specific video |
| **POST** | **`/api/attention/snapshot`** | **Camera frame → ML → attention score** |
| GET | `/api/attention/dummy-snapshot` | Test without camera |
| GET | `/api/attention/history` | Session attention logs |
| GET | `/api/transcription/{id}` | Full video transcript |
| GET | `/api/transcription/{id}/live` | Segment at timestamp |
| POST | `/api/transcription/chunk` | Transcribe audio chunk |
| **POST** | **`/api/assessment/generate`** | **Generate adaptive quiz** |
| **POST** | **`/api/assessment/submit`** | **Submit answers → get adaptive result (now includes CSR breakdown)** |
| GET | `/api/csr/{student_id}` | Most recent Cognitive Readiness Score record |
| GET | `/api/csr/{student_id}/history` | Full CSR history (every component + fused score) |
| GET | `/api/csr/{student_id}/performance/history` | Performance (P) time series |
| GET | `/api/csr/{student_id}/attention/history` | Attention (A) time series |
| GET | `/api/csr/{student_id}/integrity/history` | Response Integrity (I) time series |
| GET | `/api/csr/{student_id}/trend/history` | Learning Trend (T) time series |
| GET | `/api/csr/{student_id}/complexity/history` | Content Complexity (C) time series |
| GET | `/api/csr/{student_id}/difficulty/reason` | Latest adaptive explanation string |
| GET | `/api/leaderboard` | Global rankings |
| GET | `/api/challenges/daily` | Daily challenges |
| GET | `/api/notifications` | Student notifications |
| GET | `/health` | ML model status |

---

## Environment Variables

### Frontend (`.env.local`)
```
NEXT_PUBLIC_API_URL=http://localhost:8000/api
```

### Backend (`.env`)
```
HOST=0.0.0.0
PORT=8000
CORS_ORIGINS=http://localhost:3000
WHISPER_MODEL_SIZE=base
FLAN_T5_MODEL=google/flan-t5-base
DB_PATH=./data/neurolearn_db.json
```

---


## Video URL Support

The VideoPlayer auto-detects and handles:

| URL Type | Example | Method |
|----------|---------|--------|
| Direct MP4 | `https://example.com/video.mp4` | Native `<video>` element |
| YouTube | `youtube.com/watch?v=X` or `youtu.be/X` | Auto-converts to embed iframe |
| Any embed | Other video pages | iframe fallback |

Use the "Play Custom URL" button on the video page to paste any URL.

---

## Tech Stack

**Frontend:** Next.js 16, React 19, TypeScript, Tailwind CSS v4, Framer Motion

**Backend:** FastAPI, Pydantic, TinyDB, Loguru

**ML Models:** MediaPipe (attention), Faster Whisper (transcription), FLAN-T5 (questions)

**Adaptive Engine:** Cognitive Readiness Score (CSR) / MCL-DE — fuses Performance, Attention, Response Integrity, Learning Trend, and Content Complexity into difficulty selection (legacy rule-cascade engine retained behind a config flag)

---
## Quick Start (Full Stack — Frontend + FastAPI Backend)

### Terminal 1: Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install fastapi uvicorn tinydb loguru python-dotenv
python main.py
# → API running at http://localhost:8000
# → Swagger docs at http://localhost:8000/docs
```

### Terminal 2: Frontend
```bash
npm install
npm run dev
# → Open http://localhost:3000
```

The frontend auto-detects whether the backend is running:
- **Backend UP** → uses real FastAPI endpoints + ML models
- **Backend DOWN** → falls back to local dummy data seamlessly

---

## Testing

```bash
cd backend
pip install -r requirements.txt
pip install pytest pytest-asyncio httpx --break-system-packages   # test-only deps

# Unit tests — CSR and all 5 components (21 tests)
pytest tests/test_csr.py -v

# API / integration tests — full HTTP layer via FastAPI's TestClient
pytest tests/test_csr_api.py -v

# Everything
pytest tests/ -v
```

`tests/test_csr.py` covers each component module in isolation (Performance, Attention
sub-scores, Response Integrity, Trend, Content Complexity) plus end-to-end CSR fusion,
including a direct regression test asserting that a fast-but-*correct* response is still
penalized by the Integrity component.

`tests/test_csr_api.py` (new — see **API & Integration Tests** below) drives the actual
FastAPI app through `TestClient`: generate → submit → read back via every `/api/csr/...`
endpoint, confirming the full Phase 12 closed loop (assessment → CSR computation →
persistence → history retrieval) works over real HTTP requests, not just direct function
calls.

---

| Route | Page | Description |
|-------|------|-------------|
| `/` | Splash | Animated logo → redirect to dashboard |
| `/dashboard` | Dashboard | Course grid, XP stats, daily challenges, badges |
| `/video` | Video Learning | Video player, camera feed, attention monitor, transcription |
| `/assessment` | Assessment | Adaptive quiz with timer |
| `/results` | Results | Score gauge, XP earned, adaptive feedback |
| `/leaderboard` | Leaderboard | Global rankings with podium |
| `/profile` | Profile | Student info, achievements, stats |

