# NeuroLearn Backend — Adaptive Learning Platform

## Architecture

```
backend/
├── main.py                 # FastAPI app entry point
├── .env                    # Environment configuration
├── requirements.txt        # Python dependencies
│
├── schemas/
│   └── models.py           # Pydantic models (JSON schemas)
│
├── routers/
│   ├── student.py          # Student profile, XP, badges
│   ├── courses.py          # Course listing, video links
│   ├── attention.py        # Camera behavioral-cue monitoring
│   ├── transcription.py    # Video transcription (Whisper)
│   ├── assessment.py       # Quiz generation + submission
│   └── gamification.py     # Leaderboard, challenges, notifications
│
├── ml/
│   ├── attention_model.py  # MediaPipe face mesh → behavioral-cue score
│   ├── transcription_model.py # Whisper → transcript segments
│   ├── question_generator.py  # FLAN-T5 → quiz questions
│   └── adaptive_engine.py  # Score + behavioral cue → next difficulty
│
└── data/
    └── database.py         # TinyDB dummy database + seed data
```

## Quick Start

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activatet  # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run server
python main.py
# OR
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## API Docs

Once running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## ML Model Pipeline

```
Student Opens Video
       ↓
Video Playback Starts
       ↓
Camera + Transcript Collection
  ├── Camera frames → POST /api/attention/snapshot
  │     → MediaPipe Face Mesh
  │     → Eye tracking + Head pose + Blink rate
  │     → Behavioral Cue score (0-100) + State (attentive/inattentive/unfocused)
  │
  └── Audio → POST /api/transcription/chunk
        → OpenAI Whisper
        → Text + word timestamps + confidence
       ↓
Assessment Generation: POST /api/assessment/generate
  ├── Adaptive Engine determines difficulty
  │     (based on previous_score + attention_score)
  └── FLAN-T5 generates questions from transcript
       ↓
Student Takes Quiz
       ↓
Submit: POST /api/assessment/submit
  ├── Grade answers
  ├── Adaptive Engine analyzes performance
  │     → Performance trend (improving/stable/declining)
  │     → Time analysis
  │     → Historical pattern
  └── Returns next_difficulty + XP + recommendations
       ↓
Next Assessment Difficulty Updated
```

## Dummy Mode

All ML models gracefully fall back to dummy data if not installed.
This means the frontend can be developed and tested without:
- GPU / CUDA
- MediaPipe
- Whisper
- Transformers / FLAN-T5

The API returns realistic dummy JSON in the exact same format.

## Reproducibility Statement (live vs. dummy)

**FIX (MJ4, peer review packet):** dummy-mode output is realistic enough
to be visually indistinguishable from live-model output in a screenshot
or a report figure — the peer review packet flagged this as a risk that
demo materials could be silently dummy-driven with no reader-visible
signal. Every ML response now carries an explicit `"source"` field:

| Endpoint | `source` values |
|---|---|
| `POST /api/attention/snapshot` | `"live"` (MediaPipe ran, including the no-face case) or `"dummy"` (MediaPipe/OpenCV unavailable) |
| `POST /api/assessment/generate` (per question) | `"flan_t5_live"` or `"question_bank_fallback"` |
| `POST /api/transcription/chunk` | inherits Whisper's own availability flag — see `ml/transcription_model.py` |

Any report or figure generated from stored data (including
`NeuroLearn_ML_Metrics_Report.docx`) should be built by filtering on this
field, and should state the live/dummy mix explicitly rather than
presenting all samples as equivalent. Check `GET /health` for which
models were loaded at server start.

## Consent & Data Retention (behavioral-cue monitoring)

**FIX (CR6, peer review packet):** `/api/attention/snapshot` is
consent-gated. A student must have an on-file `granted=true` record
(`POST /api/attention/consent`) before any frame is analyzed, and the
request itself must carry `consent_confirmed=true`. Declining does not
penalize CRS — `ml/crs.py` defaults the Behavioral Cue (B) component to a
neutral 0.5 when no behavioral-cue score is supplied, so opting out only
removes a potential signal, it never forces a lower readiness score or a
harder/easier tier. Raw camera frames are analyzed in memory and are
never persisted — only the derived numeric score and sub-metrics are
written to `attention_logs`, under the retention window (default 30
days) recorded at consent time. `POST /api/attention/purge-expired`
deletes any attention_logs rows past that window; run it on a schedule
in a real deployment (there is no background job runner in the
prototype yet). This is a functional consent/retention mechanism for a
prototype, not a substitute for institutional IRB review — see the
manuscript's Ethics, Privacy, and Fairness section for what a
human-subjects deployment additionally requires.

## Key API Endpoints


### Behavioral Cue Monitoring
```bash
# With camera frame
curl -X POST http://localhost:8000/api/attention/snapshot \
  -H "Content-Type: application/json" \
  -d '{"frame_base64": "...", "video_id": "v1", "student_id": "student_001"}'

# Dummy (no camera needed)
curl http://localhost:8000/api/attention/dummy-snapshot
```

### Assessment Generation
```bash
curl -X POST http://localhost:8000/api/assessment/generate \
  -H "Content-Type: application/json" \
  -d '{
    "course_id": "course_001",
    "video_id": "v1",
    "student_id": "student_001",
    "attention_score": 75,
    "previous_score": null,
    "transcript_text": "React is a JavaScript library..."
  }'
```

### Assessment Submission
```bash
curl -X POST http://localhost:8000/api/assessment/submit \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session_abc123",
    "student_id": "student_001",
    "answers": {"q_001": 1, "q_002": 0, "q_003": 2},
    "time_spent": 180
  }'
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| HOST | 0.0.0.0 | Server host |
| PORT | 8000 | Server port |
| DEBUG | true | Enable hot reload |
| CORS_ORIGINS | http://localhost:3000 | Allowed origins |
| WHISPER_MODEL_SIZE | base | Whisper model (tiny/base/small/medium/large) |
| FLAN_T5_MODEL | google/flan-t5-base | FLAN-T5 variant |
| DB_PATH | ./data/neurolearn_db.json | TinyDB file path |

## Frontend Integration

All endpoints return JSON matching the TypeScript interfaces in `lib/api.ts`.
Replace the dummy `fetch` calls with real API calls:

```typescript
// Before (dummy):
export async function fetchAttentionScore(): Promise<AttentionSnapshot> {
  await delay(100);
  return generateAttentionSnapshot();
}

// After (real FastAPI):
export async function fetchAttentionScore(frameBase64: string): Promise<AttentionSnapshot> {
  const res = await fetch(`${API_BASE}/attention/snapshot`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      frame_base64: frameBase64,
      video_id: currentVideoId,
      student_id: currentStudentId,
    }),
  });
  return res.json();
}
```

