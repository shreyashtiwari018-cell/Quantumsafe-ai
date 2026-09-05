"""
QuantumSafe AI — FastAPI backend.

Phase 1 (analyze) + Phase 2 (persistence/reports) + Phase 3 (dashboard
summary) + Phase 4 (pattern detection) endpoints.

Run:
    uvicorn app.main:app --reload --port 8000

Then open:
    http://localhost:8000/docs
"""

import csv
import os
import sqlite3
import uuid
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.services.pipeline import analyze_report
from app.services.pattern_detection import detect_patterns


DB_PATH = os.path.join(
    os.path.dirname(__file__),
    "data",
    "quantumsafe.db"
)

MAX_CSV_BYTES = 5 * 1024 * 1024
MAX_REPORT_LENGTH = 10000

APP_VERSION = "2.0.0"

app = FastAPI(
    title="QuantumSafe AI",
    version=APP_VERSION,
    description="AI-assisted HSE safety intelligence and SIF pattern detection."
)


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# DB setup
# ---------------------------------------------------------------------------

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        yield conn
    finally:
        conn.close()



def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 210_000)
    return f"pbkdf2_sha256$210000${salt.hex()}${digest.hex()}"

def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, rounds, salt_hex, digest_hex = stored.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"),
            bytes.fromhex(salt_hex), int(rounds)
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False

def cleanup_sessions(conn):
    conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (utc_now(),))

def create_session(conn, user_id: str) -> str:
    cleanup_sessions(conn)
    token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=12)
    conn.execute(
        "INSERT INTO sessions(token_hash,user_id,created_at,expires_at) VALUES(?,?,?,?)",
        (token_hash, user_id, now.isoformat(), expires.isoformat())
    )
    return token

def get_current_user(authorization: Optional[str]):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    with get_db() as conn:
        cleanup_sessions(conn)
        row = conn.execute(
            """SELECT u.user_id,u.name,u.email,u.role,u.is_active
               FROM sessions s JOIN users u ON u.user_id=s.user_id
               WHERE s.token_hash=? AND u.is_active=1""",
            (token_hash,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="Session expired or invalid")
        return dict(row)

def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                report_id TEXT PRIMARY KEY,
                report_text TEXT NOT NULL,
                report_type TEXT,
                date TEXT,
                location TEXT,
                activity TEXT,
                hazard TEXT,
                sif_potential INTEGER,
                confidence REAL,
                risk_score INTEGER,
                risk_level TEXT,
                life_saving_rule TEXT,
                barrier_failure TEXT,
                status TEXT DEFAULT 'Open'
            )
        """)


        report_columns = {row["name"] for row in conn.execute("PRAGMA table_info(reports)").fetchall()}
        if "created_by" not in report_columns:
            conn.execute("ALTER TABLE reports ADD COLUMN created_by TEXT")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'HSE Officer',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                last_login TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        """)
        # Always ensure the SIH demo administrator exists with the known demo password.
        # This also repairs a demo account left behind by an earlier test run.
        conn.execute("""
            INSERT INTO users
            (user_id,name,email,password_hash,role,is_active,created_at)
            VALUES (?,?,?,?,?,1,?)
            ON CONFLICT(email) DO UPDATE SET
                name=excluded.name,
                password_hash=excluded.password_hash,
                role=excluded.role,
                is_active=1
        """, (
            "USR-DEMO-ADMIN",
            "QuantumSafe Admin",
            "admin@quantumsafe.ai",
            hash_password("QuantumSafe@123"),
            "HSE Administrator",
            utc_now()
        ))

        conn.commit()


@app.on_event("startup")
def on_startup():
    init_db()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    report_text: str


class SaveReportRequest(BaseModel):
    report_text: str
    report_type: Optional[str] = "NEAR_MISS"
    date: Optional[str] = None
    location: Optional[str] = "Unspecified"



class LoginRequest(BaseModel):
    email: str
    password: str

class LogoutRequest(BaseModel):
    token: str


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

@app.post("/api/auth/login")
def login(req: LoginRequest):
    email = req.email.strip().lower()
    if not email or not req.password:
        raise HTTPException(status_code=400, detail="Email and password are required")

    with get_db() as conn:
        cleanup_sessions(conn)
        user = conn.execute(
            """SELECT user_id,name,email,password_hash,role,is_active
               FROM users WHERE lower(email)=?""",
            (email,)
        ).fetchone()

        if not user or not user["is_active"] or not verify_password(req.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        token = create_session(conn, user["user_id"])
        conn.execute(
            "UPDATE users SET last_login=? WHERE user_id=?",
            (utc_now(), user["user_id"])
        )
        conn.commit()

        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": 43200,
            "user": {
                "user_id": user["user_id"],
                "name": user["name"],
                "email": user["email"],
                "role": user["role"]
            }
        }

@app.get("/api/auth/me")
def me(authorization: Optional[str] = Header(default=None)):
    return {"user": get_current_user(authorization)}

@app.post("/api/auth/logout")
def logout(req: LogoutRequest):
    token_hash = hashlib.sha256(req.token.encode("utf-8")).hexdigest()
    with get_db() as conn:
        conn.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash,))
        conn.commit()
    return {"status": "signed_out"}

# ---------------------------------------------------------------------------
# Phase 1: Analyze
# ---------------------------------------------------------------------------

@app.post("/api/reports/analyze")
def analyze(req: AnalyzeRequest, authorization: Optional[str] = Header(default=None)):
    get_current_user(authorization)

    text = req.report_text.strip()

    if not text:
        raise HTTPException(
            status_code=400,
            detail="report_text must not be empty"
        )

    if len(text) > MAX_REPORT_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"report_text exceeds the {MAX_REPORT_LENGTH} character limit"
        )

    result = analyze_report(text)

    return result.to_dict()


# ---------------------------------------------------------------------------
# Phase 2: Save Report
# ---------------------------------------------------------------------------

@app.post("/api/reports")
def save_report(
    req: SaveReportRequest,
    authorization: Optional[str] = Header(default=None)
):
    current_user = get_current_user(authorization)

    text = req.report_text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="report_text must not be empty")
    if len(text) > MAX_REPORT_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"report_text exceeds the {MAX_REPORT_LENGTH} character limit"
        )

    result = analyze_report(text)
    report_id = f"R{uuid.uuid4().hex[:8].upper()}"

    with get_db() as conn:
        conn.execute("""
            INSERT INTO reports
            (
                report_id, report_text, report_type, date, location,
                activity, hazard, sif_potential, confidence, risk_score,
                risk_level, life_saving_rule, barrier_failure, status, created_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Open', ?)
        """, (
            report_id,
            text,
            req.report_type,
            req.date,
            req.location,
            result.activity,
            result.primary_hazard,
            int(result.sif_potential),
            result.confidence,
            result.risk_score,
            result.risk_level,
            result.life_saving_rule,
            ",".join(result.failed_barriers),
            current_user["user_id"]
        ))
        conn.commit()

    return {
        "report_id": report_id,
        **result.to_dict()
    }


# ---------------------------------------------------------------------------
# List Reports
# ---------------------------------------------------------------------------

@app.get("/api/reports")
def list_reports(
    location: Optional[str] = None,
    risk_level: Optional[str] = None,
    sif_potential: Optional[int] = None,
    q: Optional[str] = None,
    hazard: Optional[str] = None,
    status: Optional[str] = None,
    sort: str = "newest",
    limit: int = 100,
    offset: int = 0,
    authorization: Optional[str] = Header(default=None)
):
    get_current_user(authorization)
    limit = max(1, min(limit, 500))
    offset = max(0, offset)

    query = "SELECT * FROM reports WHERE 1=1"
    params = []

    if location:
        query += " AND location = ?"
        params.append(location)

    if risk_level:
        query += " AND risk_level = ?"
        params.append(risk_level.upper())

    if sif_potential is not None:
        query += " AND sif_potential = ?"
        params.append(sif_potential)

    if q:
        query += " AND (report_id LIKE ? OR report_text LIKE ? OR hazard LIKE ? OR location LIKE ?)"
        term = f"%{q}%"
        params.extend([term, term, term, term])

    if hazard:
        query += " AND hazard = ?"
        params.append(hazard)

    if status:
        query += " AND status = ?"
        params.append(status)

    sort_map = {
        "newest": "rowid DESC",
        "oldest": "rowid ASC",
        "risk_high": "risk_score DESC, rowid DESC",
        "risk_low": "risk_score ASC, rowid DESC",
    }
    query += " ORDER BY " + sort_map.get(sort, sort_map["newest"])
    query += " LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Get Single Report
# ---------------------------------------------------------------------------

@app.get("/api/reports/{report_id}")
def get_report(report_id: str, authorization: Optional[str] = Header(default=None)):
    get_current_user(authorization)

    with get_db() as conn:

        row = conn.execute(
            "SELECT * FROM reports WHERE report_id = ?",
            (report_id,)
        ).fetchone()

        if not row:
            raise HTTPException(
                status_code=404,
                detail="Report not found"
            )

        return dict(row)



# ---------------------------------------------------------------------------
# Investigation status
# ---------------------------------------------------------------------------

class StatusUpdateRequest(BaseModel):
    status: str

@app.patch("/api/reports/{report_id}/status")
def update_report_status(
    report_id: str,
    req: StatusUpdateRequest,
    authorization: Optional[str] = Header(default=None)
):
    current_user = get_current_user(authorization)
    allowed = {"Open", "Under Review", "Investigation", "Action Required", "Resolved"}
    status = req.status.strip()
    if status not in allowed:
        raise HTTPException(status_code=400, detail="Invalid investigation status")

    with get_db() as conn:
        row = conn.execute("SELECT report_id FROM reports WHERE report_id=?", (report_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Report not found")
        conn.execute("UPDATE reports SET status=? WHERE report_id=?", (status, report_id))
        conn.commit()

    return {"report_id": report_id, "status": status, "updated_by": current_user["user_id"]}

# ---------------------------------------------------------------------------
# CSV Upload
# ---------------------------------------------------------------------------

@app.post("/api/reports/upload")
async def upload_csv(file: UploadFile = File(...), authorization: Optional[str] = Header(default=None)):
    get_current_user(authorization)
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file selected")

    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a CSV file")

    content = await file.read()

    if len(content) > MAX_CSV_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"CSV exceeds the {MAX_CSV_BYTES // (1024 * 1024)} MB upload limit"
        )

    try:
        decoded = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="CSV must be UTF-8 encoded"
        )

    reader = csv.DictReader(decoded.splitlines())

    if not reader.fieldnames or "report_text" not in reader.fieldnames:
        raise HTTPException(
            status_code=400,
            detail="CSV must contain a 'report_text' column"
        )

    saved = 0
    skipped = 0
    duplicates = 0
    invalid_rows = []

    with get_db() as conn:
        for row_number, row in enumerate(reader, start=2):
            text = (row.get("report_text") or "").strip()

            if not text:
                skipped += 1
                invalid_rows.append({
                    "row": row_number,
                    "reason": "Missing report_text"
                })
                continue

            if len(text) > MAX_REPORT_LENGTH:
                skipped += 1
                invalid_rows.append({
                    "row": row_number,
                    "reason": f"report_text exceeds {MAX_REPORT_LENGTH} characters"
                })
                continue

            existing = conn.execute(
                "SELECT report_id FROM reports WHERE report_text = ? LIMIT 1",
                (text,)
            ).fetchone()

            if existing:
                duplicates += 1
                continue

            result = analyze_report(text)
            report_id = f"R{uuid.uuid4().hex[:8].upper()}"

            conn.execute("""
                INSERT INTO reports
                (
                    report_id, report_text, report_type, date, location,
                    activity, hazard, sif_potential, confidence, risk_score,
                    risk_level, life_saving_rule, barrier_failure, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Open')
            """, (
                report_id,
                text,
                row.get("report_type", "UNSPECIFIED"),
                row.get("date"),
                row.get("location", "Unspecified"),
                result.activity,
                result.primary_hazard,
                int(result.sif_potential),
                result.confidence,
                result.risk_score,
                result.risk_level,
                result.life_saving_rule,
                ";".join(result.failed_barriers),
            ))

            saved += 1

        conn.commit()

    return {
        "saved": saved,
        "duplicates": duplicates,
        "skipped": skipped,
        "invalid_rows": invalid_rows[:25],
        "total_rows_processed": saved + duplicates + skipped,
    }


# ---------------------------------------------------------------------------
# Phase 3: Dashboard
# ---------------------------------------------------------------------------

@app.get("/api/dashboard/summary")
def dashboard_summary(authorization: Optional[str] = Header(default=None)):
    get_current_user(authorization)
    with get_db() as conn:
        total = conn.execute(
            "SELECT COUNT(*) c FROM reports"
        ).fetchone()["c"]

        sif = conn.execute(
            "SELECT COUNT(*) c FROM reports WHERE sif_potential = 1"
        ).fetchone()["c"]

        critical = conn.execute(
            "SELECT COUNT(*) c FROM reports WHERE risk_level = 'CRITICAL'"
        ).fetchone()["c"]

        high = conn.execute(
            "SELECT COUNT(*) c FROM reports WHERE risk_level = 'HIGH'"
        ).fetchone()["c"]

        medium = conn.execute(
            "SELECT COUNT(*) c FROM reports WHERE risk_level = 'MEDIUM'"
        ).fetchone()["c"]

        low = conn.execute(
            "SELECT COUNT(*) c FROM reports WHERE risk_level = 'LOW'"
        ).fetchone()["c"]

        near_miss = conn.execute(
            "SELECT COUNT(*) c FROM reports WHERE report_type = 'NEAR_MISS'"
        ).fetchone()["c"]

        top_hazards = conn.execute("""
            SELECT COALESCE(hazard, 'Unclassified') hazard, COUNT(*) c
            FROM reports
            GROUP BY hazard
            ORDER BY c DESC
            LIMIT 5
        """).fetchall()

        top_locations = conn.execute("""
            SELECT COALESCE(location, 'Unspecified') location, COUNT(*) c
            FROM reports
            WHERE sif_potential = 1
            GROUP BY location
            ORDER BY c DESC
            LIMIT 5
        """).fetchall()

        top_rules = conn.execute("""
            SELECT COALESCE(life_saving_rule, 'Unclassified') life_saving_rule, COUNT(*) c
            FROM reports
            GROUP BY life_saving_rule
            ORDER BY c DESC
            LIMIT 5
        """).fetchall()

        barrier_rows = conn.execute("""
            SELECT barrier_failure
            FROM reports
            WHERE barrier_failure IS NOT NULL
              AND barrier_failure != ''
        """).fetchall()

        barrier_counts = {}
        for row in barrier_rows:
            for barrier in str(row["barrier_failure"]).replace(",", ";").split(";"):
                barrier = barrier.strip()
                if barrier:
                    barrier_counts[barrier] = barrier_counts.get(barrier, 0) + 1

        top_barriers = [
            {"barrier": name, "c": count}
            for name, count in sorted(
                barrier_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]
        ]

        recent = conn.execute("""
            SELECT report_id, location, hazard, risk_level, risk_score,
                   sif_potential, status, rowid
            FROM reports
            ORDER BY rowid DESC
            LIMIT 8
        """).fetchall()

    return {
        "total_reports": total,
        "sif_potential": sif,
        "sif_percentage": round((sif / total * 100), 1) if total else 0,
        "critical": critical,
        "high_risk": high,
        "medium_risk": medium,
        "low_risk": low,
        "near_miss": near_miss,
        "risk_distribution": {
            "CRITICAL": critical,
            "HIGH": high,
            "MEDIUM": medium,
            "LOW": low,
        },
        "top_hazards": [dict(row) for row in top_hazards],
        "top_high_risk_locations": [dict(row) for row in top_locations],
        "top_life_saving_rules": [dict(row) for row in top_rules],
        "top_failed_barriers": top_barriers,
        "recent_reports": [dict(row) for row in recent],
    }


@app.get("/api/health")
def health():
    with get_db() as conn:
        report_count = conn.execute(
            "SELECT COUNT(*) c FROM reports"
        ).fetchone()["c"]

    return {
        "status": "ok",
        "service": "QuantumSafe AI",
        "version": APP_VERSION,
        "database": "connected",
        "report_count": report_count,
    }


# ---------------------------------------------------------------------------
# Phase 4: Pattern Detection
# ---------------------------------------------------------------------------

@app.get("/api/patterns")
def get_patterns(min_reports: int = 3, authorization: Optional[str] = Header(default=None)):
    get_current_user(authorization)

    with get_db() as conn:

        rows = conn.execute(
            "SELECT * FROM reports"
        ).fetchall()

        reports = [dict(row) for row in rows]

    patterns = detect_patterns(
        reports,
        min_reports=min_reports
    )

    return [
        {
            "hazard": p.hazard,
            "location": p.location,
            "failed_barrier": p.failed_barrier,
            "report_count": p.report_count,
            "sif_count": p.sif_count,
            "sif_ratio": round(p.sif_ratio, 2),
            "risk": p.risk,
            "report_ids": p.report_ids,
        }
        for p in patterns
    ]


# ---------------------------------------------------------------------------
# Root
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "QuantumSafe AI backend"
    }