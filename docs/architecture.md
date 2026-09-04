# ExamGuard Architecture

## Project Structure

```
ExamGuard/
├── backend/                  # FastAPI application
│   ├── app/
│   │   ├── api/              # Route handlers (thin controllers)
│   │   │   └── v1/           # Versioned API endpoints
│   │   ├── core/             # Config, security, settings
│   │   ├── models/           # SQLAlchemy ORM models
│   │   ├── schemas/          # Pydantic request/response schemas
│   │   ├── services/         # Business logic
│   │   │   ├── exam/         # Exam verification service
│   │   │   ├── attendance/   # Attendance service
│   │   │   ├── document/     # OCR, hall-ticket extraction
│   │   │   ├── erp/          # ERP integration abstraction
│   │   │   └── signal_detection.py  # Anti-proxy signal detection
│   │   ├── ai/               # AI perception layer (face, UniFace wrappers)
│   │   ├── storage/          # Storage abstraction (local, Cloudinary later)
│   │   └── main.py           # FastAPI app factory
│   ├── alembic/              # Database migrations
│   ├── alembic.ini
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile (future)
├── frontend/                 # Next.js application
│   ├── src/
│   │   ├── app/              # Next.js App Router pages
│   │   ├── components/       # Reusable UI components
│   │   ├── lib/              # API client, utilities
│   │   └── styles/           # Global styles, theme config
│   ├── public/
│   ├── package.json
│   ├── tsconfig.json
│   └── tailwind.config.ts
├── docs/                     # Architecture docs, API docs
├── .env.example
├── .gitignore
└── README.md
```

## Key Architectural Principles

```
AI Layer        →  PERCEPTION only (what does the camera see?)
Database        →  SOURCE OF TRUTH (all config, identity, state)
Business Logic  →  AUTHORIZATION & DECISIONS (is this student allowed?)
Frontend        →  USER INTERACTION (display, input, navigation)
Storage         →  ABSTRACTED (swap providers without code changes)
```

## Separation of Concerns

- **AI Layer**: Detects faces, computes embeddings, checks liveness. Returns structured data.
- **Business Logic**: Makes authorization decisions based on AI output + database state.
- **Database**: Stores all configuration, student data, exam schedules, verification events.
- **Frontend**: Displays information and collects user input. Communicates via REST API only.

## Future Phase Integration Points

| Phase | Integration Point |
|---|---|
| UniFace | `backend/app/ai/face.py` |
| OCR | `backend/app/services/document/` |
| Seating | `backend/app/models/` + `services/` |
| Cameras | `backend/app/models/` + `services/` |
| Anti-Proxy Signals | `backend/app/services/signal_detection.py` |
| Attendance | `backend/app/services/attendance/` |
| Cloudinary | `backend/app/storage/cloudinary.py` |
| ERP | `backend/app/services/erp/adapter.py` |
| WebSockets | `backend/app/api/v1/ws/` |

## Configuration Philosophy

ALL configuration is database-driven. The system must NEVER hard-code:

- Student names, USNs, hall-ticket numbers
- Exam names, subjects, dates, times
- Departments, semesters
- Hall assignments, seating arrangements
- Camera IDs, camera-to-hall mappings
- AI thresholds
- ERP information
