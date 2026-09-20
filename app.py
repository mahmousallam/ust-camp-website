from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory, send_file
from flask_cors import CORS
import psycopg2
import psycopg2.extras
import re
import requests
import os
import io
import secrets
import string
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from reportlab.lib.pagesizes import landscape, A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}, r"/uploads/*": {"origins": "*"}, r"/materials/*": {"origins": "*"}})
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")
app.permanent_session_lifetime = timedelta(days=365)
app.config["SESSION_REFRESH_EACH_REQUEST"] = True

DB_NAME = "camp.db"
UPLOAD_FOLDER = "uploads"
MATERIALS_FOLDER = "materials"
ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "docx", "pptx", "xlsx", "mp4", "mov"}
SESSION_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(MATERIALS_FOLDER, exist_ok=True)

# ---------- إعدادات Supabase (قاعدة البيانات + تخزين الملفات) ----------
# دول لازم تتحطوا كـ Environment Variables على السيرفر (Render). متكتبهمش هنا مباشرة.
DATABASE_URL = os.environ.get("DATABASE_URL")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")  # مثال: https://xxxx.supabase.co
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
SUPABASE_BUCKET = os.environ.get("SUPABASE_BUCKET", "uploads")


def upload_to_storage(file_storage, dest_filename):
    """
    بيرفع ملف لتخزين Supabase، وبيرجع الرابط العام (Public URL) بتاعه.
    لو إعدادات Supabase مش متظبطة (يعني بتشتغل محليًا للتجربة)، بيرجع لحفظ محلي عادي.
    """
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        local_path = os.path.join(UPLOAD_FOLDER, dest_filename)
        file_storage.save(local_path)
        return f"/{local_path}"

    file_bytes = file_storage.read()
    content_type = file_storage.mimetype or "application/octet-stream"
    upload_url = f"{SUPABASE_URL}/storage/v1/object/{SUPABASE_BUCKET}/{dest_filename}"
    headers = {
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "apikey": SUPABASE_SERVICE_KEY,
        "Content-Type": content_type,
        "x-upsert": "true",
    }
    resp = requests.post(upload_url, headers=headers, data=file_bytes, timeout=30)
    resp.raise_for_status()
    return f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/{dest_filename}"


# روابط السوشيال ميديا - لينكدإن هيتحط لاحقًا
SOCIAL_LINKS = {
    "facebook": "https://www.facebook.com/profile.php?id=61570675637708",
    "instagram": "https://www.instagram.com/ust_menoufiauniversity",
    "youtube": "https://www.youtube.com/@USTmenufiaUniversity",
    "linkedin": "https://www.linkedin.com/company/undergraduated-scientists-training/?viewAsMember=true",  # هيتحط لاحقًا
}

OFFICIAL_EMAIL = "ust.menoufiauniversity@gmail.com"


@app.context_processor
def inject_social_links():
    return {"social_links": SOCIAL_LINKS}


@app.before_request
def refresh_student_session():
    if session.get("student_id"):
        session.permanent = True
        session.modified = True


# ---------- إعدادات عامة (تقدر تعدلها) ----------

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "camp2026")
REGISTRATION_DEADLINE = datetime(2026, 10, 15, 23, 59)

TRACK_SEAT_LIMITS = {
    "Biotechnology": 60,
    "Food Science": 60,
    "Microbiology": 60,
    "Soil": 40,
    "Animal Production": 40,
    "Plant": 40,
}

ACTIVITY_POINTS = {
    "حضور ورشة": 10,
    "المشاركة في نقاش": 5,
    "حضور زيارة": 15,
    "التطوع في تنظيم فعالية": 20,
    "إكمال مشروع صغير": 30,
    "الفوز في مسابقة": 50,
    "مساعدة زميل (منتورينج)": 15,
}

LEVELS = [
    (0, "مبتدئ", "Bronze"),
    (50, "نشيط", "Silver"),
    (150, "متميز", "Gold"),
    (300, "بطل البرنامج", "Platinum"),
]

# نسبة إكمال الـ Assignments المطلوبة لاستخراج الشهادة
CERTIFICATE_THRESHOLD = 0.75

# إعدادات إرسال الإيميل (اختياري) - حط القيم دي كـ Environment Variables على السيرفر
# مقترح: SMTP_USER يبقى الإيميل الرسمي ust.menoufiauniversity@gmail.com + App Password بتاعه
SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASS = os.environ.get("SMTP_PASS")
SMTP_FROM = os.environ.get("SMTP_FROM", SMTP_USER)

MODULES = [
    {"number": 1, "title": "Career Foundation", "desc": "Orientation, Team Building, LinkedIn, CV Writing, Email Etiquette, Communication Skills"},
    {"number": 2, "title": "Digital Skills", "desc": "AI Tools, Excel, Google Workspace, Canva, Git & GitHub, أساسيات الأمن الرقمي"},
    {"number": 3, "title": "Scientific Skills", "desc": "Scientific Research Basics, Google Scholar, PubMed, Zotero/Mendeley, Presentation Skills"},
    {"number": 4, "title": "Practical Skills (Hands-on)", "desc": "تطبيق عملي حسب المسار: Biotechnology, Food Science, Microbiology, Soil, Animal Production, Plant"},
    {"number": 5, "title": "Industry Exposure", "desc": "زيارة شركة أغذية، مزرعة حديثة، مركز أبحاث، جلسة HR، لقاء مع خريجين"},
    {"number": 6, "title": "Career Preparation", "desc": "Interview Skills, Personal Branding, Scholarships, Internships, Freelancing Basics"},
]

TRACKS = list(TRACK_SEAT_LIMITS.keys())


def level_for_points(points):
    current_name, current_badge = LEVELS[0][1], LEVELS[0][2]
    for threshold, name, badge in LEVELS:
        if points >= threshold:
            current_name, current_badge = name, badge
    return current_name, current_badge


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def generate_access_code():
    return "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))


BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "").strip()
BREVO_SENDER_EMAIL = os.environ.get("BREVO_SENDER_EMAIL", OFFICIAL_EMAIL).strip()


def send_email(to_email, subject, body):
    """إرسال البريد عبر Brevo عند توفره، أو SMTP كخيار بديل."""
    if BREVO_API_KEY:
        try:
            resp = requests.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={
                    "accept": "application/json",
                    "api-key": BREVO_API_KEY,
                    "content-type": "application/json",
                },
                json={
                    "sender": {"name": "UST Menoufia Program", "email": BREVO_SENDER_EMAIL},
                    "to": [{"email": to_email}],
                    "subject": subject,
                    "textContent": body,
                },
                timeout=15,
            )
            if 200 <= resp.status_code < 300:
                return True
            app.logger.error("Brevo email failed: status=%s response=%s", resp.status_code, resp.text[:500])
            return False
        except requests.RequestException:
            app.logger.exception("Brevo email request failed")
            return False

    if not SMTP_HOST or not SMTP_USER or not SMTP_PASS:
        return False
    try:
        message = MIMEText(body, "plain", "utf-8")
        message["Subject"] = subject
        message["From"] = SMTP_FROM or SMTP_USER
        message["To"] = to_email
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as smtp:
            smtp.starttls()
            smtp.login(SMTP_USER, SMTP_PASS)
            smtp.sendmail(message["From"], [to_email], message.as_string())
        return True
    except (OSError, smtplib.SMTPException):
        app.logger.exception("SMTP email failed")
        return False


def send_registration_email(to_email, full_name, access_code):
    """يحاول يبعت إيميل تأكيد. لو الإعدادات مش موجودة، بيتجاهل بهدوء والكود بيفضل ظاهر على الشاشة."""
    body = (
        f"أهلاً {full_name}،\n\n"
        f"تم تسجيلك بنجاح في البرنامج.\n"
        f"كود الدخول لأكونتك: {access_code}\n\n"
        f"سجّل دخولك من هنا: (رابط الموقع)/student/login\n"
    )
    return send_email(to_email, "تم تسجيلك في البرنامج - كود الدخول", body)


# ---------- طبقة الاتصال بقاعدة بيانات PostgreSQL (Supabase) ----------
# الطبقة دي بتخلي أوامر SQL القديمة (بعلامة ?) تشتغل عادي مع PostgreSQL
# من غير ما نحتاج نعيد كتابة كل سطر SQL في الملف كله.

class PGCursorWrapper:
    """يلف الـ cursor بتاع psycopg2 عشان نقدر نستخدم fetchone()/fetchall() زي المعتاد"""
    def __init__(self, cursor):
        self._cursor = cursor

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()


class FakeIdCursor:
    """بيرجع آخر id اتعمله INSERT - بديل last_insert_rowid() بتاعة SQLite"""
    def __init__(self, last_id):
        self._last_id = last_id

    def fetchone(self):
        return {"id": self._last_id}

    def fetchall(self):
        return [{"id": self._last_id}]


class PGConnection:
    def __init__(self, pg_conn):
        self._conn = pg_conn
        self._last_id = None

    def execute(self, sql, params=()):
        stripped = sql.strip()

        # التوافق مع سطر "SELECT last_insert_rowid()" القديم بتاع SQLite
        if stripped.upper().startswith("SELECT LAST_INSERT_ROWID()"):
            return FakeIdCursor(self._last_id)

        # PRAGMA بتاعة SQLite مالهاش معنى في PostgreSQL - نتجاهلها
        if stripped.upper().startswith("PRAGMA"):
            return FakeIdCursor(None)

        pg_sql = stripped.replace("?", "%s")

        cur = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        is_insert = re.match(r"(?i)^\s*INSERT\s+INTO", pg_sql) is not None
        has_returning = "RETURNING" in pg_sql.upper()

        if is_insert and not has_returning:
            pg_sql += " RETURNING id"

        cur.execute(pg_sql, params)

        if is_insert and not has_returning:
            try:
                row = cur.fetchone()
                if row:
                    self._last_id = row["id"]
            except psycopg2.ProgrammingError:
                pass

        return PGCursorWrapper(cur)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


def get_db():
    pg_conn = psycopg2.connect(DATABASE_URL)
    return PGConnection(pg_conn)


def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS teams (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id SERIAL PRIMARY KEY,
            full_name TEXT NOT NULL,
            college TEXT NOT NULL,
            specialization TEXT NOT NULL,
            level TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT NOT NULL,
            whatsapp TEXT,
            track TEXT,
            notes TEXT,
            access_code TEXT,
            team_id INTEGER REFERENCES teams(id),
            show_on_leaderboard INTEGER DEFAULT 1,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("ALTER TABLE students ADD COLUMN IF NOT EXISTS avatar_url TEXT")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id SERIAL PRIMARY KEY,
            module_number INTEGER NOT NULL,
            title TEXT NOT NULL,
            instructor TEXT,
            session_date TEXT,
            description TEXT,
            recording_url TEXT,
            material_url TEXT,
            assignment_text TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("ALTER TABLE sessions ADD COLUMN IF NOT EXISTS image_url TEXT")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            id SERIAL PRIMARY KEY,
            student_id INTEGER NOT NULL REFERENCES students(id),
            session_id INTEGER REFERENCES sessions(id),
            sub_type TEXT NOT NULL,
            title TEXT NOT NULL,
            content_text TEXT,
            file_path TEXT,
            points_awarded INTEGER DEFAULT 0,
            submitted_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS points_log (
            id SERIAL PRIMARY KEY,
            student_id INTEGER NOT NULL REFERENCES students(id),
            activity TEXT NOT NULL,
            points INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS badges_log (
            id SERIAL PRIMARY KEY,
            student_id INTEGER NOT NULL REFERENCES students(id),
            badge_name TEXT NOT NULL,
            awarded_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS session_comments (
            id SERIAL PRIMARY KEY,
            session_id INTEGER NOT NULL REFERENCES sessions(id),
            student_id INTEGER NOT NULL REFERENCES students(id),
            comment_text TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS moments (
            id SERIAL PRIMARY KEY,
            student_id INTEGER NOT NULL REFERENCES students(id),
            caption TEXT,
            file_path TEXT NOT NULL,
            is_approved INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS moment_views (
            id SERIAL PRIMARY KEY,
            moment_id INTEGER NOT NULL REFERENCES moments(id),
            viewer_student_id INTEGER NOT NULL REFERENCES students(id),
            viewed_at TEXT NOT NULL,
            UNIQUE(moment_id, viewer_student_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS moment_likes (
            id SERIAL PRIMARY KEY,
            moment_id INTEGER NOT NULL REFERENCES moments(id),
            student_id INTEGER NOT NULL REFERENCES students(id),
            liked_at TEXT NOT NULL,
            UNIQUE(moment_id, student_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS session_ratings (
            id SERIAL PRIMARY KEY,
            session_id INTEGER NOT NULL REFERENCES sessions(id),
            student_id INTEGER NOT NULL REFERENCES students(id),
            rating INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(session_id, student_id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS committee_members (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            committee TEXT NOT NULL,
            photo_url TEXT,
            created_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS member_spotlight (
            id SERIAL PRIMARY KEY,
            member_id INTEGER NOT NULL REFERENCES committee_members(id),
            set_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS track_messages (
            id SERIAL PRIMARY KEY,
            track TEXT NOT NULL,
            student_id INTEGER NOT NULL REFERENCES students(id),
            message_text TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS api_tokens (
            id SERIAL PRIMARY KEY,
            token TEXT UNIQUE NOT NULL,
            student_id INTEGER NOT NULL REFERENCES students(id),
            created_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


if DATABASE_URL:
    init_db()


def student_total_points(conn, student_id):
    row = conn.execute(
        "SELECT COALESCE(SUM(points), 0) AS total FROM points_log WHERE student_id = ?",
        (student_id,)
    ).fetchone()
    return row["total"]


def compute_progress(conn, student_id):
    """نسبة إكمال الـ Assignments المطلوبة"""
    total_required = conn.execute(
        "SELECT COUNT(*) AS c FROM sessions WHERE assignment_text IS NOT NULL AND assignment_text != ''"
    ).fetchone()["c"]
    if total_required == 0:
        return 0, 0, 0
    completed = conn.execute("""
        SELECT COUNT(DISTINCT session_id) AS c FROM submissions
        WHERE student_id = ? AND sub_type = 'assignment' AND session_id IS NOT NULL
    """, (student_id,)).fetchone()["c"]
    pct = round((completed / total_required) * 100)
    return pct, completed, total_required


def compute_streak(conn, student_id):
    """عدد السيشنز المتتالية (بالترتيب) اللي الطالب سلّم فيها assignment، محسوبة من الأحدث للأقدم"""
    sessions_ordered = conn.execute("""
        SELECT id FROM sessions
        WHERE assignment_text IS NOT NULL AND assignment_text != ''
        ORDER BY session_date DESC, id DESC
    """).fetchall()
    submitted_ids = {
        r["session_id"] for r in conn.execute(
            "SELECT DISTINCT session_id FROM submissions WHERE student_id = ? AND sub_type = 'assignment'",
            (student_id,)
        ).fetchall()
    }
    streak = 0
    for s in sessions_ordered:
        if s["id"] in submitted_ids:
            streak += 1
        else:
            break
    return streak


def check_and_award_badges(conn, student_id):
    """يفحص ويضيف بادجات المستوى تلقائيًا لو الطالب وصلها لأول مرة"""
    total_points = student_total_points(conn, student_id)
    _, badge_tier = level_for_points(total_points)
    already = conn.execute(
        "SELECT 1 FROM badges_log WHERE student_id = ? AND badge_name = ?",
        (student_id, badge_tier)
    ).fetchone()
    if not already:
        conn.execute(
            "INSERT INTO badges_log (student_id, badge_name, awarded_at) VALUES (?, ?, ?)",
            (student_id, badge_tier, datetime.now().strftime("%Y-%m-%d %H:%M"))
        )
        conn.commit()

def get_best_instructor(conn):
    """أفضل محاضر حسب متوسط تقييم آخر 7 أيام"""
    cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M")
    row = conn.execute("""
        SELECT sess.instructor, AVG(r.rating) AS avg_rating, COUNT(r.id) AS num_ratings
        FROM session_ratings r
        JOIN sessions sess ON sess.id = r.session_id
        WHERE r.created_at >= ? AND sess.instructor IS NOT NULL AND sess.instructor != ''
        GROUP BY sess.instructor
        HAVING COUNT(r.id) >= 1
        ORDER BY avg_rating DESC
        LIMIT 1
    """, (cutoff,)).fetchone()
    if not row:
        return None
    return {"instructor": row["instructor"], "avg_rating": round(float(row["avg_rating"]), 1), "num_ratings": row["num_ratings"]}


def get_active_spotlight(conn):
    """عضو اللجنة المُبرَز حاليًا (لو اتحدد خلال آخر 24 ساعة)"""
    cutoff = (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M")
    row = conn.execute("""
        SELECT ms.*, cm.name, cm.committee, cm.photo_url FROM member_spotlight ms
        JOIN committee_members cm ON cm.id = ms.member_id
        WHERE ms.set_at >= ?
        ORDER BY ms.set_at DESC LIMIT 1
    """, (cutoff,)).fetchone()
    if not row:
        return None
    return {"name": row["name"], "committee": row["committee"], "photo_url": row["photo_url"]}


def get_active_stories(conn, viewer_id):
    """اللحظات المعتمدة خلال آخر 24 ساعة، مجمّعة حسب الطالب"""
    cutoff = (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M")
    rows = conn.execute("""
        SELECT m.*, s.full_name, s.avatar_url FROM moments m
        JOIN students s ON s.id = m.student_id
        WHERE m.is_approved = 1 AND m.created_at >= ?
        ORDER BY m.student_id, m.created_at
    """, (cutoff,)).fetchall()

    grouped = {}
    for r in rows:
        sid = r["student_id"]
        if sid not in grouped:
            grouped[sid] = {"student_id": sid, "student_name": r["full_name"], "avatar_url": r["avatar_url"], "moments": [], "is_mine": (viewer_id == sid)}
        seen = False
        liked = False
        if viewer_id:
            seen = conn.execute(
                "SELECT 1 FROM moment_views WHERE moment_id = ? AND viewer_student_id = ?",
                (r["id"], viewer_id)
            ).fetchone() is not None
            liked = conn.execute(
                "SELECT 1 FROM moment_likes WHERE moment_id = ? AND student_id = ?",
                (r["id"], viewer_id)
            ).fetchone() is not None
        likes_count = conn.execute(
            "SELECT COUNT(*) AS c FROM moment_likes WHERE moment_id = ?", (r["id"],)
        ).fetchone()["c"]
        file_path = r["file_path"]
        if file_path and not file_path.startswith(("/", "http://", "https://")):
            file_path = "/" + file_path
        grouped[sid]["moments"].append({
            "id": r["id"], "caption": r["caption"], "file_path": file_path,
            "created_at": r["created_at"], "seen": seen, "liked": liked, "likes_count": likes_count
        })

    stories = list(grouped.values())
    for s in stories:
        latest_image = next(
            (moment["file_path"] for moment in reversed(s["moments"])
             if moment["file_path"].lower().split("?")[0].rsplit(".", 1)[-1] in SESSION_IMAGE_EXTENSIONS),
            None,
        )
        s["story_avatar_url"] = s["avatar_url"] or latest_image
        s["has_unseen"] = any(not m["seen"] for m in s["moments"])
        if s["is_mine"]:
            moment_ids = [m["id"] for m in s["moments"]]
            if moment_ids:
                placeholders = ",".join(["?"] * len(moment_ids))
                count_row = conn.execute(
                    f"SELECT COUNT(DISTINCT viewer_student_id) AS c FROM moment_views WHERE moment_id IN ({placeholders})",
                    tuple(moment_ids)
                ).fetchone()
                s["views_count"] = count_row["c"]
            else:
                s["views_count"] = 0
        else:
            s["views_count"] = None
    return stories


# ---------- الصفحات العامة ----------

@app.route("/")
def home():
    registration_open = datetime.now() <= REGISTRATION_DEADLINE
    conn = get_db()
    best_instructor = get_best_instructor(conn)
    spotlight = get_active_spotlight(conn)
    conn.close()
    return render_template("index.html", modules=MODULES, registration_open=registration_open,
                            deadline=REGISTRATION_DEADLINE, best_instructor=best_instructor, spotlight=spotlight)


@app.route("/register", methods=["GET", "POST"])
def register():
    registration_open = datetime.now() <= REGISTRATION_DEADLINE
    if not registration_open:
        return render_template("register_closed.html", deadline=REGISTRATION_DEADLINE)

    conn = get_db()

    track_availability = {}
    for t, limit in TRACK_SEAT_LIMITS.items():
        count = conn.execute("SELECT COUNT(*) AS c FROM students WHERE track = ?", (t,)).fetchone()["c"]
        track_availability[t] = {"limit": limit, "taken": count, "full": (limit is not None and count >= limit)}

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        college = request.form.get("college", "").strip()
        specialization = request.form.get("specialization", "").strip()
        level = request.form.get("level", "").strip()
        phone = request.form.get("phone", "").strip()
        whatsapp = request.form.get("whatsapp", "").strip()
        email = request.form.get("email", "").strip()
        track = request.form.get("track", "").strip()
        notes = request.form.get("notes", "").strip()

        if not full_name or not college or not specialization or not phone or not email:
            flash("من فضلك املأ كل الحقول المطلوبة", "error")
            conn.close()
            return render_template("register.html", tracks=TRACKS, track_availability=track_availability)

        existing = conn.execute(
            "SELECT id FROM students WHERE email = ? OR phone = ?", (email, phone)
        ).fetchone()
        if existing:
            flash("الإيميل أو رقم التليفون ده مسجل قبل كده", "error")
            conn.close()
            return render_template("register.html", tracks=TRACKS, track_availability=track_availability)

        if track and track_availability.get(track, {}).get("full"):
            flash(f"للأسف مسار {track} اكتمل عدده. اختار مسار تاني.", "error")
            conn.close()
            return render_template("register.html", tracks=TRACKS, track_availability=track_availability)

        access_code = generate_access_code()

        conn.execute(
            """INSERT INTO students
               (full_name, college, specialization, level, phone, whatsapp, email, track, notes, access_code, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (full_name, college, specialization, level, phone, whatsapp, email, track, notes,
             access_code, datetime.now().strftime("%Y-%m-%d %H:%M"))
        )
        conn.commit()
        conn.close()

        email_sent = send_registration_email(email, full_name, access_code)

        return render_template("thank_you.html", access_code=access_code, email=email, email_sent=email_sent)

    conn.close()
    return render_template("register.html", tracks=TRACKS, track_availability=track_availability)


@app.route("/leaderboard")
def leaderboard():
    period = request.args.get("period", "all")  # 'all' or 'month'
    view = request.args.get("view", "individual")  # 'individual' or 'team'

    conn = get_db()

    if period == "month":
        start_of_month = datetime.now().replace(day=1, hour=0, minute=0, second=0).strftime("%Y-%m-%d %H:%M")
        points_filter = "AND p.created_at >= ?"
        params = [start_of_month]
    else:
        points_filter = ""
        params = []

    if view == "team":
        query = f"""
            SELECT t.id, t.name, COALESCE(SUM(p.points), 0) AS total_points
            FROM teams t
            LEFT JOIN students s ON s.team_id = t.id
            LEFT JOIN points_log p ON p.student_id = s.id {points_filter}
            GROUP BY t.id
            ORDER BY total_points DESC
        """
        rows = conn.execute(query, params).fetchall()
        board = [{"name": r["name"], "points": r["total_points"]} for r in rows]
    else:
        query = f"""
            SELECT s.id, s.full_name, s.track, COALESCE(SUM(p.points), 0) AS total_points
            FROM students s
            LEFT JOIN points_log p ON p.student_id = s.id {points_filter}
            WHERE s.show_on_leaderboard = 1
            GROUP BY s.id
            ORDER BY total_points DESC
            LIMIT 20
        """
        rows = conn.execute(query, params).fetchall()
        board = [{"name": r["full_name"], "track": r["track"], "points": r["total_points"],
                  "level": level_for_points(r["total_points"])[0]} for r in rows]

    conn.close()
    return render_template("leaderboard.html", board=board, period=period, view=view)


# ---------- بوابة الطالب ----------

@app.route("/student/login", methods=["GET", "POST"])
def student_login():
    if request.method == "GET" and session.get("student_id"):
        return redirect(url_for("student_dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        access_code = request.form.get("access_code", "").strip().upper()

        conn = get_db()
        student = conn.execute(
            "SELECT * FROM students WHERE email = ? AND access_code = ?", (email, access_code)
        ).fetchone()
        conn.close()

        if student:
            session.permanent = True
            session["student_id"] = student["id"]
            return redirect(url_for("student_dashboard"))
        else:
            flash("الإيميل أو الكود غلط", "error")

    return render_template("student_login.html")


@app.route("/student/logout")
def student_logout():
    session.pop("student_id", None)
    return redirect(url_for("home"))


def current_student(conn):
    sid = session.get("student_id")
    if not sid:
        return None
    return conn.execute("SELECT * FROM students WHERE id = ?", (sid,)).fetchone()


@app.route("/student/dashboard")
def student_dashboard():
    conn = get_db()
    student = current_student(conn)
    if not student:
        conn.close()
        return redirect(url_for("student_login"))

    total_points = student_total_points(conn, student["id"])
    check_and_award_badges(conn, student["id"])
    level_name, _ = level_for_points(total_points)
    progress_pct, completed, total_required = compute_progress(conn, student["id"])
    streak = compute_streak(conn, student["id"])

    points_history = conn.execute(
        "SELECT * FROM points_log WHERE student_id = ? ORDER BY created_at DESC", (student["id"],)
    ).fetchall()
    sessions_list = conn.execute("SELECT * FROM sessions ORDER BY module_number, session_date").fetchall()
    my_submissions = conn.execute(
        "SELECT * FROM submissions WHERE student_id = ? ORDER BY submitted_at DESC", (student["id"],)
    ).fetchall()
    my_badges = conn.execute(
        "SELECT * FROM badges_log WHERE student_id = ? ORDER BY awarded_at", (student["id"],)
    ).fetchall()
    team = None
    if student["team_id"]:
        team = conn.execute("SELECT * FROM teams WHERE id = ?", (student["team_id"],)).fetchone()

    certificate_eligible = progress_pct >= (CERTIFICATE_THRESHOLD * 100)
    stories = get_active_stories(conn, student["id"])
    my_active_moments = [m for m in stories if m["student_id"] == student["id"]]
    my_active_moments = my_active_moments[0]["moments"] if my_active_moments else []

    conn.close()

    submitted_session_ids = {s["session_id"] for s in my_submissions if s["session_id"]}

    return render_template(
        "student_dashboard.html",
        student=student,
        total_points=total_points,
        level=level_name,
        points_history=points_history,
        sessions_list=sessions_list,
        my_submissions=my_submissions,
        submitted_session_ids=submitted_session_ids,
        progress_pct=progress_pct,
        completed=completed,
        total_required=total_required,
        streak=streak,
        my_badges=my_badges,
        team=team,
        certificate_eligible=certificate_eligible,
        my_active_moments=my_active_moments,
    )


@app.route("/student/settings", methods=["POST"])
def student_settings():
    conn = get_db()
    student = current_student(conn)
    if not student:
        conn.close()
        return redirect(url_for("student_login"))

    show_on_leaderboard = 1 if request.form.get("show_on_leaderboard") == "on" else 0
    conn.execute("UPDATE students SET show_on_leaderboard = ? WHERE id = ?", (show_on_leaderboard, student["id"]))
    conn.commit()
    conn.close()
    flash("تم تحديث إعداداتك", "success")
    return redirect(url_for("student_dashboard"))


@app.route("/student/avatar", methods=["POST"])
def student_avatar():
    conn = get_db()
    student = current_student(conn)
    if not student:
        conn.close()
        return redirect(url_for("student_login"))

    photo = request.files.get("avatar")
    extension = photo.filename.rsplit(".", 1)[-1].lower() if photo and photo.filename else ""
    if not photo or not photo.filename or extension not in SESSION_IMAGE_EXTENSIONS:
        flash("اختار صورة بصيغة PNG أو JPG أو JPEG", "error")
        conn.close()
        return redirect(url_for("student_dashboard"))

    filename = secure_filename(f"avatar_{student['id']}_{secrets.token_hex(4)}.{extension}")
    avatar_url = upload_to_storage(photo, filename)
    conn.execute("UPDATE students SET avatar_url = ? WHERE id = ?", (avatar_url, student["id"]))
    conn.commit()
    conn.close()
    flash("تم تحديث صورة الحساب", "success")
    return redirect(url_for("student_dashboard"))


@app.route("/student/session/<int:session_id>", methods=["GET", "POST"])
def student_session_detail(session_id):
    conn = get_db()
    student = current_student(conn)
    if not student:
        conn.close()
        return redirect(url_for("student_login"))

    session_row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if not session_row:
        conn.close()
        flash("السيشن مش موجودة", "error")
        return redirect(url_for("student_dashboard"))

    if request.method == "POST":
        form_type = request.form.get("form_type", "assignment")

        if form_type == "comment":
            comment_text = request.form.get("comment_text", "").strip()
            if comment_text:
                conn.execute(
                    "INSERT INTO session_comments (session_id, student_id, comment_text, created_at) VALUES (?, ?, ?, ?)",
                    (session_id, student["id"], comment_text, datetime.now().strftime("%Y-%m-%d %H:%M"))
                )
                conn.commit()
        else:
            content_text = request.form.get("content_text", "").strip()
            file = request.files.get("file")
            file_path = None

            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(f"{student['id']}_{session_id}_{file.filename}")
                file_path = upload_to_storage(file, filename)

            conn.execute(
                """INSERT INTO submissions (student_id, session_id, sub_type, title, content_text, file_path, submitted_at)
                   VALUES (?, ?, 'assignment', ?, ?, ?, ?)""",
                (student["id"], session_id, f"Assignment - {session_row['title']}", content_text, file_path,
                 datetime.now().strftime("%Y-%m-%d %H:%M"))
            )
            conn.commit()
            flash("تم تسليم الـ Assignment بنجاح", "success")

        conn.close()
        return redirect(url_for("student_session_detail", session_id=session_id))

    comments = conn.execute("""
        SELECT c.*, s.full_name FROM session_comments c
        JOIN students s ON s.id = c.student_id
        WHERE c.session_id = ? ORDER BY c.created_at
    """, (session_id,)).fetchall()

    conn.close()
    return render_template("session_detail.html", s=session_row, comments=comments)

@app.route("/student/session/<int:session_id>/rate", methods=["POST"])
def student_session_rate(session_id):
    conn = get_db()
    student = current_student(conn)
    if not student:
        conn.close()
        return redirect(url_for("student_login"))

    rating = request.form.get("rating")
    try:
        rating = int(rating)
    except (TypeError, ValueError):
        rating = None

    if rating and 1 <= rating <= 5:
        conn.execute("""
            INSERT INTO session_ratings (session_id, student_id, rating, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (session_id, student_id) DO UPDATE SET rating = EXCLUDED.rating, created_at = EXCLUDED.created_at
        """, (session_id, student["id"], rating, datetime.now().strftime("%Y-%m-%d %H:%M")))
        conn.commit()
        flash("شكرًا لتقييمك", "success")

    conn.close()
    return redirect(url_for("student_session_detail", session_id=session_id))

@app.route("/student/track-chat")
def student_track_chat():
    conn = get_db()
    student = current_student(conn)
    if not student:
        conn.close()
        return redirect(url_for("student_login"))

    if not student["track"]:
        conn.close()
        flash("لازم يكون عندك مسار محدد عشان تدخل الجروب", "error")
        return redirect(url_for("student_dashboard"))

    messages = conn.execute("""
        SELECT tm.*, s.full_name FROM track_messages tm
        JOIN students s ON s.id = tm.student_id
        WHERE tm.track = ? ORDER BY tm.created_at
    """, (student["track"],)).fetchall()
    conn.close()
    return render_template("track_chat.html", track=student["track"], messages=messages)


@app.route("/student/track-chat/send", methods=["POST"])
def student_track_chat_send():
    conn = get_db()
    student = current_student(conn)
    if not student or not student["track"]:
        conn.close()
        return redirect(url_for("student_dashboard"))

    text = request.form.get("message_text", "").strip()
    if text:
        conn.execute(
            "INSERT INTO track_messages (track, student_id, message_text, created_at) VALUES (?, ?, ?, ?)",
            (student["track"], student["id"], text, datetime.now().strftime("%Y-%m-%d %H:%M"))
        )
        conn.commit()
    conn.close()
    return redirect(url_for("student_track_chat"))


@app.route("/student/upload", methods=["GET", "POST"])
def student_upload():
    conn = get_db()
    student = current_student(conn)
    if not student:
        conn.close()
        return redirect(url_for("student_login"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        sub_type = request.form.get("sub_type", "documentation")
        content_text = request.form.get("content_text", "").strip()
        file = request.files.get("file")
        file_path = None

        if not title:
            flash("من فضلك اكتب عنوان للتوثيق", "error")
            conn.close()
            return redirect(url_for("student_upload"))

        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(f"{student['id']}_{secrets.token_hex(4)}_{file.filename}")
            file_path = upload_to_storage(file, filename)

        conn.execute(
            """INSERT INTO submissions (student_id, session_id, sub_type, title, content_text, file_path, submitted_at)
               VALUES (?, NULL, ?, ?, ?, ?, ?)""",
            (student["id"], sub_type, title, content_text, file_path,
             datetime.now().strftime("%Y-%m-%d %H:%M"))
        )
        conn.commit()
        conn.close()
        flash("تم رفع التوثيق بنجاح", "success")
        return redirect(url_for("student_dashboard"))

    conn.close()
    return render_template("student_upload.html")


@app.route("/student/certificate")
def student_certificate():
    conn = get_db()
    student = current_student(conn)
    if not student:
        conn.close()
        return redirect(url_for("student_login"))

    progress_pct, completed, total_required = compute_progress(conn, student["id"])
    conn.close()

    if progress_pct < (CERTIFICATE_THRESHOLD * 100):
        flash("لسه معملتش نسبة الإكمال الكافية لاستخراج الشهادة", "error")
        return redirect(url_for("student_dashboard"))

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=landscape(A4))
    width, height = landscape(A4)

    c.setFillColorRGB(0.12, 0.23, 0.37)
    c.rect(0, 0, width, height, fill=1)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 32)
    c.drawCentredString(width / 2, height - 4 * cm, "Certificate of Completion")
    c.setFont("Helvetica", 18)
    c.drawCentredString(width / 2, height - 6 * cm, "This certifies that")
    c.setFont("Helvetica-Bold", 26)
    c.drawCentredString(width / 2, height - 8 * cm, student["full_name"])
    c.setFont("Helvetica", 16)
    c.drawCentredString(width / 2, height - 10 * cm, "has successfully completed the UST Menoufia University Career & Skills Program")
    c.setFont("Helvetica", 12)
    c.drawCentredString(width / 2, height - 12 * cm, f"Completion rate: {progress_pct}%  |  Date: {datetime.now().strftime('%Y-%m-%d')}")
    c.save()
    buf.seek(0)

    return send_file(buf, mimetype="application/pdf", as_attachment=True,
                      download_name=f"certificate_{student['full_name']}.pdf")


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


@app.route("/admin/moments/<int:moment_id>/download")
def admin_moment_download(moment_id):
    if not require_admin():
        return redirect(url_for("admin_login"))

    conn = get_db()
    moment = conn.execute("SELECT file_path FROM moments WHERE id = ?", (moment_id,)).fetchone()
    conn.close()
    if not moment:
        flash("اللحظة مش موجودة", "error")
        return redirect(url_for("admin_moments"))

    file_path = moment["file_path"]
    filename = file_path.rsplit("/", 1)[-1]
    if file_path.startswith("/uploads/"):
        return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True, download_name=filename)

    try:
        response = requests.get(file_path, timeout=30)
        response.raise_for_status()
    except requests.RequestException:
        flash("تعذر تنزيل ملف اللحظة من التخزين", "error")
        return redirect(url_for("admin_moments"))

    return send_file(
        io.BytesIO(response.content),
        mimetype=response.headers.get("Content-Type", "application/octet-stream"),
        as_attachment=True,
        download_name=filename,
    )


@app.route("/materials/<path:filename>")
def material_file(filename):
    return send_from_directory(MATERIALS_FOLDER, filename)


# ---------- لوحة الإدارة ----------

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        password = request.form.get("password", "")
        if password == ADMIN_PASSWORD:
            session["is_admin"] = True
            return redirect(url_for("admin_dashboard"))
        else:
            flash("كلمة السر غلط", "error")
    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("home"))


def require_admin():
    return session.get("is_admin", False)


@app.route("/admin")
def admin_dashboard():
    if not require_admin():
        return redirect(url_for("admin_login"))

    conn = get_db()
    students = conn.execute("SELECT * FROM students ORDER BY created_at DESC").fetchall()
    conn.close()

    specialization_counts = {}
    track_counts = {}
    for s in students:
        specialization_counts[s["specialization"]] = specialization_counts.get(s["specialization"], 0) + 1
        t = s["track"] or "لسه محددش"
        track_counts[t] = track_counts.get(t, 0) + 1

    return render_template(
        "admin.html",
        students=students,
        total=len(students),
        specialization_counts=specialization_counts,
        track_counts=track_counts
    )


@app.route("/admin/delete/<int:student_id>")
def admin_delete(student_id):
    if not require_admin():
        return redirect(url_for("admin_login"))

    conn = get_db()
    conn.execute("DELETE FROM moment_views WHERE viewer_student_id = ?", (student_id,))
    conn.execute("DELETE FROM moment_views WHERE moment_id IN (SELECT id FROM moments WHERE student_id = ?)", (student_id,))
    conn.execute("DELETE FROM moments WHERE student_id = ?", (student_id,))
    conn.execute("DELETE FROM session_comments WHERE student_id = ?", (student_id,))
    conn.execute("DELETE FROM submissions WHERE student_id = ?", (student_id,))
    conn.execute("DELETE FROM points_log WHERE student_id = ?", (student_id,))
    conn.execute("DELETE FROM badges_log WHERE student_id = ?", (student_id,))
    conn.execute("DELETE FROM api_tokens WHERE student_id = ?", (student_id,))
    conn.execute("DELETE FROM students WHERE id = ?", (student_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/export")
def admin_export():
    if not require_admin():
        return redirect(url_for("admin_login"))

    import csv
    from flask import Response

    conn = get_db()
    students = conn.execute("SELECT * FROM students ORDER BY created_at DESC").fetchall()
    conn.close()

    output = io.StringIO()
    output.write('\ufeff')
    writer = csv.writer(output)
    writer.writerow(["الاسم", "الكلية", "التخصص", "الفرقة", "المسار", "التليفون", "الواتساب", "الإيميل", "ملاحظات", "تاريخ التسجيل"])
    for s in students:
        writer.writerow([s["full_name"], s["college"], s["specialization"], s["level"], s["track"],
                          s["phone"], s["whatsapp"], s["email"], s["notes"], s["created_at"]])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=students.csv"}
    )


# ---------- إدارة السيشنز ----------

@app.route("/admin/sessions")
def admin_sessions():
    if not require_admin():
        return redirect(url_for("admin_login"))
    conn = get_db()
    sessions_list = conn.execute("SELECT * FROM sessions ORDER BY module_number, session_date").fetchall()
    conn.close()
    return render_template("admin_sessions.html", sessions_list=sessions_list, modules=MODULES)


@app.route("/admin/sessions/new", methods=["GET", "POST"])
def admin_session_new():
    if not require_admin():
        return redirect(url_for("admin_login"))

    if request.method == "POST":
        module_number = request.form.get("module_number")
        title = request.form.get("title", "").strip()
        session_date = request.form.get("session_date", "").strip()
        instructor = request.form.get("instructor", "").strip()
        description = request.form.get("description", "").strip()
        recording_url = request.form.get("recording_url", "").strip()
        material_url = request.form.get("material_url", "").strip()
        assignment_text = request.form.get("assignment_text", "").strip()

        if not title or not module_number:
            flash("لازم تحدد اسم السيشن والمديول", "error")
            return render_template("admin_session_form.html", modules=MODULES)

        session_image = request.files.get("session_image")
        image_url = None

        if session_image and session_image.filename:
            image_extension = session_image.filename.rsplit(".", 1)[-1].lower() if "." in session_image.filename else ""
            if image_extension not in SESSION_IMAGE_EXTENSIONS:
                flash("صورة السيشن لازم تكون PNG أو JPG أو JPEG أو WEBP", "error")
                return render_template("admin_session_form.html", modules=MODULES)
            filename = secure_filename(f"session_{secrets.token_hex(8)}.{image_extension}")
            image_url = upload_to_storage(session_image, filename)

        conn = get_db()
        conn.execute(
            """INSERT INTO sessions (module_number, title, session_date, instructor, description, recording_url, material_url, assignment_text, image_url, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (module_number, title, session_date, instructor, description, recording_url, material_url, assignment_text,
             image_url, datetime.now().strftime("%Y-%m-%d %H:%M"))
        )
        conn.commit()
        conn.close()
        flash("تمت إضافة السيشن", "success")
        return redirect(url_for("admin_sessions"))

    return render_template("admin_session_form.html", modules=MODULES)


@app.route("/admin/sessions/delete/<int:session_id>")
def admin_session_delete(session_id):
    if not require_admin():
        return redirect(url_for("admin_login"))
    conn = get_db()
    conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_sessions"))


# ---------- إدارة النقاط والبادجات ----------

@app.route("/admin/points", methods=["GET", "POST"])
def admin_points():
    if not require_admin():
        return redirect(url_for("admin_login"))

    conn = get_db()

    if request.method == "POST":
        form_type = request.form.get("form_type", "points")
        student_id = request.form.get("student_id")

        if form_type == "badge":
            badge_name = request.form.get("badge_name", "").strip()
            if student_id and badge_name:
                conn.execute(
                    "INSERT INTO badges_log (student_id, badge_name, awarded_at) VALUES (?, ?, ?)",
                    (student_id, badge_name, datetime.now().strftime("%Y-%m-%d %H:%M"))
                )
                conn.commit()
                flash("تم منح البادج", "success")
        else:
            activity = request.form.get("activity", "").strip()
            custom_points = request.form.get("custom_points", "").strip()

            points = ACTIVITY_POINTS.get(activity)
            if points is None and custom_points:
                try:
                    points = int(custom_points)
                except ValueError:
                    points = None

            if not student_id or points is None:
                flash("اختار الطالب والنشاط أو حدد نقاط مخصصة", "error")
            else:
                conn.execute(
                    "INSERT INTO points_log (student_id, activity, points, created_at) VALUES (?, ?, ?, ?)",
                    (student_id, activity or f"نقاط مخصصة ({points})", points, datetime.now().strftime("%Y-%m-%d %H:%M"))
                )
                conn.commit()
                check_and_award_badges(conn, student_id)
                flash("تم تسجيل النقاط", "success")

    students = conn.execute("SELECT id, full_name, email FROM students ORDER BY full_name").fetchall()
    recent_log = conn.execute("""
        SELECT p.*, s.full_name FROM points_log p
        JOIN students s ON s.id = p.student_id
        ORDER BY p.created_at DESC LIMIT 30
    """).fetchall()
    recent_badges = conn.execute("""
        SELECT b.*, s.full_name FROM badges_log b
        JOIN students s ON s.id = b.student_id
        ORDER BY b.awarded_at DESC LIMIT 20
    """).fetchall()
    conn.close()

    return render_template(
        "admin_points.html",
        students=students,
        activities=ACTIVITY_POINTS,
        recent_log=recent_log,
        recent_badges=recent_badges,
    )


@app.route("/admin/submissions")
def admin_submissions():
    if not require_admin():
        return redirect(url_for("admin_login"))

    conn = get_db()
    submissions = conn.execute("""
        SELECT sub.*, s.full_name, s.email
        FROM submissions sub
        JOIN students s ON s.id = sub.student_id
        ORDER BY sub.submitted_at DESC
    """).fetchall()
    conn.close()
    return render_template("admin_submissions.html", submissions=submissions)


@app.route("/admin/submissions/grade/<int:submission_id>", methods=["POST"])
def admin_submission_grade(submission_id):
    if not require_admin():
        return redirect(url_for("admin_login"))

    points = request.form.get("points", "").strip()
    conn = get_db()
    sub = conn.execute("SELECT * FROM submissions WHERE id = ?", (submission_id,)).fetchone()

    if sub and points:
        try:
            points_val = int(points)
            conn.execute("UPDATE submissions SET points_awarded = ? WHERE id = ?", (points_val, submission_id))
            conn.execute(
                "INSERT INTO points_log (student_id, activity, points, created_at) VALUES (?, ?, ?, ?)",
                (sub["student_id"], f"تقييم: {sub['title']}", points_val, datetime.now().strftime("%Y-%m-%d %H:%M"))
            )
            conn.commit()
            check_and_award_badges(conn, sub["student_id"])
            flash("تم تسجيل التقييم والنقاط", "success")
        except ValueError:
            flash("النقاط لازم تكون رقم", "error")

    conn.close()
    return redirect(url_for("admin_submissions"))


# ---------- إدارة الفرق ----------

@app.route("/admin/teams", methods=["GET", "POST"])
def admin_teams():
    if not require_admin():
        return redirect(url_for("admin_login"))

    conn = get_db()

    if request.method == "POST":
        form_type = request.form.get("form_type")
        if form_type == "new_team":
            name = request.form.get("name", "").strip()
            if name:
                conn.execute("INSERT INTO teams (name, created_at) VALUES (?, ?)",
                             (name, datetime.now().strftime("%Y-%m-%d %H:%M")))
                conn.commit()
        elif form_type == "assign":
            student_id = request.form.get("student_id")
            team_id = request.form.get("team_id") or None
            conn.execute("UPDATE students SET team_id = ? WHERE id = ?", (team_id, student_id))
            conn.commit()

    teams = conn.execute("SELECT * FROM teams ORDER BY name").fetchall()
    students = conn.execute("SELECT id, full_name, team_id FROM students ORDER BY full_name").fetchall()
    conn.close()

    return render_template("admin_teams.html", teams=teams, students=students)


# ---------- تحليلات ومتابعة الانقطاع ----------

@app.route("/admin/committee", methods=["GET", "POST"])
def admin_committee():
    if not require_admin():
        return redirect(url_for("admin_login"))

    conn = get_db()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        committee = request.form.get("committee", "").strip()
        photo = request.files.get("photo")
        photo_url = None
        if photo and photo.filename and allowed_file(photo.filename):
            filename = secure_filename(f"committee_{secrets.token_hex(4)}_{photo.filename}")
            photo_url = upload_to_storage(photo, filename)
        if name and committee:
            conn.execute(
                "INSERT INTO committee_members (name, committee, photo_url, created_at) VALUES (?, ?, ?, ?)",
                (name, committee, photo_url, datetime.now().strftime("%Y-%m-%d %H:%M"))
            )
            conn.commit()
            flash("تمت إضافة العضو", "success")

    members = conn.execute("SELECT * FROM committee_members ORDER BY name").fetchall()
    current_spotlight = get_active_spotlight(conn)
    conn.close()
    return render_template("admin_committee.html", members=members, current_spotlight=current_spotlight)


@app.route("/admin/committee/spotlight/<int:member_id>")
def admin_committee_spotlight(member_id):
    if not require_admin():
        return redirect(url_for("admin_login"))
    conn = get_db()
    conn.execute(
        "INSERT INTO member_spotlight (member_id, set_at) VALUES (?, ?)",
        (member_id, datetime.now().strftime("%Y-%m-%d %H:%M"))
    )
    conn.commit()
    conn.close()
    flash("تم تعيين نجم الأسبوع", "success")
    return redirect(url_for("admin_committee"))


@app.route("/admin/analytics")
def admin_analytics():
    if not require_admin():
        return redirect(url_for("admin_login"))

    conn = get_db()
    students = conn.execute("SELECT * FROM students").fetchall()

    at_risk = []
    for s in students:
        last_activity = conn.execute("""
            SELECT MAX(submitted_at) AS last FROM submissions WHERE student_id = ?
        """, (s["id"],)).fetchone()["last"]

        days_inactive = None
        if last_activity:
            last_dt = datetime.strptime(last_activity, "%Y-%m-%d %H:%M")
            days_inactive = (datetime.now() - last_dt).days
        else:
            days_inactive = (datetime.now() - datetime.strptime(s["created_at"], "%Y-%m-%d %H:%M")).days

        progress_pct, completed, total_required = compute_progress(conn, s["id"])

        if days_inactive is not None and days_inactive >= 14:
            at_risk.append({
                "name": s["full_name"], "email": s["email"], "days_inactive": days_inactive,
                "progress_pct": progress_pct
            })

    at_risk.sort(key=lambda x: x["days_inactive"], reverse=True)
    conn.close()

    return render_template("admin_analytics.html", at_risk=at_risk, total_students=len(students))


@app.route("/admin/bulk-email", methods=["GET", "POST"])
def admin_bulk_email():
    if not require_admin():
        return redirect(url_for("admin_login"))

    conn = get_db()
    students = conn.execute("SELECT * FROM students").fetchall()

    result = None
    if request.method == "POST":
        subject = request.form.get("subject", "").strip()
        body = request.form.get("body", "").strip()
        filter_track = request.form.get("filter_track", "").strip()

        if not (BREVO_API_KEY or (SMTP_HOST and SMTP_USER and SMTP_PASS)):
            flash("إعدادات الإيميل مش متظبطة على السيرفر", "error")
        elif not subject or not body:
            flash("لازم تكتب الموضوع والرسالة", "error")
        else:
            targets = [s for s in students if not filter_track or s["track"] == filter_track]
            sent, failed = 0, 0
            for s in targets:
                personalized_body = body.replace("{الاسم}", s["full_name"])
                ok = send_email(s["email"], subject, personalized_body)
                if ok:
                    sent += 1
                else:
                    failed += 1
            result = {"sent": sent, "failed": failed, "total": len(targets)}
            flash(f"تم الإرسال لـ {sent} من {len(targets)}", "success" if failed == 0 else "error")

    conn.close()
    return render_template("admin_bulk_email.html", tracks=TRACKS, result=result,
                            smtp_configured=bool(BREVO_API_KEY or (SMTP_HOST and SMTP_USER and SMTP_PASS)))


@app.route("/moments")
def moments_gallery():
    conn = get_db()
    viewer_id = session.get("student_id")
    stories = get_active_stories(conn, viewer_id)
    conn.close()
    return render_template("moments_gallery.html", stories=stories,
                            is_logged_in=bool(viewer_id))


@app.route("/student/moment/view/<int:moment_id>", methods=["POST"])
def student_moment_view(moment_id):
    conn = get_db()
    student = current_student(conn)
    if not student:
        conn.close()
        return {"ok": False}, 401

    conn.execute(
        "INSERT INTO moment_views (moment_id, viewer_student_id, viewed_at) VALUES (?, ?, ?) ON CONFLICT (moment_id, viewer_student_id) DO NOTHING",
        (moment_id, student["id"], datetime.now().strftime("%Y-%m-%d %H:%M"))
    )
    conn.commit()
    views_count = conn.execute(
        "SELECT COUNT(DISTINCT viewer_student_id) AS c FROM moment_views WHERE moment_id = ?",
        (moment_id,)
    ).fetchone()["c"]
    conn.close()
    return {"ok": True, "views_count": views_count}

@app.route("/student/moment/<int:moment_id>/like", methods=["POST"])
def student_moment_like(moment_id):
    conn = get_db()
    student = current_student(conn)
    if not student:
        conn.close()
        return {"ok": False}, 401

    already = conn.execute(
        "SELECT 1 FROM moment_likes WHERE moment_id = ? AND student_id = ?",
        (moment_id, student["id"])
    ).fetchone()

    if already:
        conn.execute(
            "DELETE FROM moment_likes WHERE moment_id = ? AND student_id = ?",
            (moment_id, student["id"])
        )
        liked = False
    else:
        conn.execute(
            "INSERT INTO moment_likes (moment_id, student_id, liked_at) VALUES (?, ?, ?)",
            (moment_id, student["id"], datetime.now().strftime("%Y-%m-%d %H:%M"))
        )
        liked = True

    conn.commit()
    likes_count = conn.execute(
        "SELECT COUNT(*) AS c FROM moment_likes WHERE moment_id = ?", (moment_id,)
    ).fetchone()["c"]
    conn.close()
    return {"ok": True, "liked": liked, "likes_count": likes_count}


@app.route("/student/moment/<int:moment_id>/delete", methods=["POST"])
def student_moment_delete_own(moment_id):
    conn = get_db()
    student = current_student(conn)
    if not student:
        conn.close()
        return {"ok": False}, 401

    moment = conn.execute("SELECT * FROM moments WHERE id = ?", (moment_id,)).fetchone()
    if not moment or moment["student_id"] != student["id"]:
        conn.close()
        return {"ok": False, "error": "دي مش لحظتك"}, 403

    conn.execute("DELETE FROM moment_likes WHERE moment_id = ?", (moment_id,))
    conn.execute("DELETE FROM moment_views WHERE moment_id = ?", (moment_id,))
    conn.execute("DELETE FROM moments WHERE id = ?", (moment_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


@app.route("/student/moment/<int:moment_id>/viewers")
def student_moment_viewers(moment_id):
    conn = get_db()
    student = current_student(conn)
    if not student:
        conn.close()
        return redirect(url_for("student_login"))

    moment = conn.execute("SELECT * FROM moments WHERE id = ?", (moment_id,)).fetchone()
    if not moment or moment["student_id"] != student["id"]:
        conn.close()
        flash("مينفعش تشوف مين شاف لحظة مش بتاعتك", "error")
        return redirect(url_for("student_dashboard"))

    viewers = conn.execute("""
        SELECT v.viewed_at, s.full_name FROM moment_views v
        JOIN students s ON s.id = v.viewer_student_id
        WHERE v.moment_id = ? ORDER BY v.viewed_at DESC
    """, (moment_id,)).fetchall()
    conn.close()
    return render_template("moment_viewers.html", moment=moment, viewers=viewers)


@app.route("/student/moments/new", methods=["GET", "POST"])
def student_moment_new():
    conn = get_db()
    student = current_student(conn)
    if not student:
        conn.close()
        return redirect(url_for("student_login"))

    if request.method == "POST":
        caption = request.form.get("caption", "").strip()
        file = request.files.get("file")

        if not file or not file.filename or not allowed_file(file.filename):
            flash("لازم ترفع صورة أو فيديو بصيغة مدعومة", "error")
            conn.close()
            return redirect(url_for("student_moment_new"))

        filename = secure_filename(f"moment_{student['id']}_{secrets.token_hex(4)}_{file.filename}")
        file_path = upload_to_storage(file, filename)

        conn.execute(
            "INSERT INTO moments (student_id, caption, file_path, is_approved, created_at) VALUES (?, ?, ?, 1, ?)",
            (student["id"], caption, file_path, datetime.now().strftime("%Y-%m-%d %H:%M"))
        )
        conn.commit()
        conn.close()
        flash("تم رفع اللحظة، هتظهر في المعرض العام بعد موافقة الأدمن", "success")
        return redirect(url_for("student_dashboard"))

    conn.close()
    return render_template("student_moment_new.html")


@app.route("/admin/moments")
def admin_moments():
    if not require_admin():
        return redirect(url_for("admin_login"))

    conn = get_db()
    pending = conn.execute("""
        SELECT m.*, s.full_name FROM moments m
        JOIN students s ON s.id = m.student_id
        WHERE m.is_approved = 0 ORDER BY m.created_at DESC
    """).fetchall()
    approved = conn.execute("""
        SELECT m.*, s.full_name FROM moments m
        JOIN students s ON s.id = m.student_id
        WHERE m.is_approved = 1 ORDER BY m.created_at DESC
    """).fetchall()
    conn.close()
    return render_template("admin_moments.html", pending=pending, approved=approved)


@app.route("/admin/moments/approve/<int:moment_id>")
def admin_moment_approve(moment_id):
    if not require_admin():
        return redirect(url_for("admin_login"))
    conn = get_db()
    conn.execute("UPDATE moments SET is_approved = 1 WHERE id = ?", (moment_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_moments"))


@app.route("/admin/moments/delete/<int:moment_id>")
def admin_moment_delete(moment_id):
    if not require_admin():
        return redirect(url_for("admin_login"))
    conn = get_db()
    conn.execute("DELETE FROM moment_views WHERE moment_id = ?", (moment_id,))
    conn.execute("DELETE FROM moments WHERE id = ?", (moment_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_moments"))


# =====================================================================
# API - للتطبيق (Mobile App) - كل ده منفصل عن صفحات الموقع العادية
# =====================================================================

from functools import wraps
from flask import jsonify, g


def api_student_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "محتاج تسجل دخول"}), 401
        token = auth.replace("Bearer ", "").strip()

        conn = get_db()
        row = conn.execute(
            "SELECT s.* FROM api_tokens t JOIN students s ON s.id = t.student_id WHERE t.token = ?",
            (token,)
        ).fetchone()
        if not row:
            conn.close()
            return jsonify({"error": "الجلسة منتهية، سجل دخول تاني"}), 401

        g.api_student = row
        g.api_conn = conn
        result = f(*args, **kwargs)
        conn.close()
        return result
    return decorated


@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or request.form
    email = (data.get("email") or "").strip()
    access_code = (data.get("access_code") or "").strip().upper()

    conn = get_db()
    student = conn.execute(
        "SELECT * FROM students WHERE email = ? AND access_code = ?", (email, access_code)
    ).fetchone()

    if not student:
        conn.close()
        return jsonify({"error": "الإيميل أو الكود غلط"}), 401

    token = secrets.token_hex(24)
    conn.execute(
        "INSERT INTO api_tokens (token, student_id, created_at) VALUES (?, ?, ?)",
        (token, student["id"], datetime.now().strftime("%Y-%m-%d %H:%M"))
    )
    conn.commit()
    conn.close()

    return jsonify({
        "token": token,
        "student": {"id": student["id"], "full_name": student["full_name"], "track": student["track"]}
    })


@app.route("/api/dashboard")
@api_student_required
def api_dashboard():
    conn = g.api_conn
    student = g.api_student

    total_points = student_total_points(conn, student["id"])
    level_name, badge_tier = level_for_points(total_points)
    progress_pct, completed, total_required = compute_progress(conn, student["id"])
    streak = compute_streak(conn, student["id"])

    team = None
    if student["team_id"]:
        t = conn.execute("SELECT * FROM teams WHERE id = ?", (student["team_id"],)).fetchone()
        team = t["name"] if t else None

    return jsonify({
        "full_name": student["full_name"],
        "track": student["track"],
        "total_points": total_points,
        "level": level_name,
        "badge_tier": badge_tier,
        "progress_pct": progress_pct,
        "completed": completed,
        "total_required": total_required,
        "streak": streak,
        "team": team,
        "certificate_eligible": progress_pct >= (CERTIFICATE_THRESHOLD * 100),
    })


@app.route("/api/sessions")
@api_student_required
def api_sessions():
    conn = g.api_conn
    student = g.api_student

    sessions_list = conn.execute("SELECT * FROM sessions ORDER BY module_number, session_date").fetchall()
    submitted_ids = {
        r["session_id"] for r in conn.execute(
            "SELECT DISTINCT session_id FROM submissions WHERE student_id = ? AND sub_type = 'assignment'",
            (student["id"],)
        ).fetchall()
    }

    result = []
    for s in sessions_list:
        result.append({
            "id": s["id"], "module_number": s["module_number"], "title": s["title"],
            "instructor": s["instructor"], "session_date": s["session_date"],
            "has_assignment": bool(s["assignment_text"]),
            "submitted": s["id"] in submitted_ids,
        })
    return jsonify(result)


@app.route("/api/sessions/<int:session_id>")
@api_student_required
def api_session_detail(session_id):
    conn = g.api_conn
    s = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if not s:
        return jsonify({"error": "مش موجودة"}), 404

    comments = conn.execute("""
        SELECT c.comment_text, c.created_at, st.full_name FROM session_comments c
        JOIN students st ON st.id = c.student_id
        WHERE c.session_id = ? ORDER BY c.created_at
    """, (session_id,)).fetchall()

    return jsonify({
        "id": s["id"], "title": s["title"], "instructor": s["instructor"],
        "module_number": s["module_number"], "session_date": s["session_date"],
        "description": s["description"], "recording_url": s["recording_url"],
        "material_url": s["material_url"], "assignment_text": s["assignment_text"],
        "comments": [{"name": c["full_name"], "text": c["comment_text"], "date": c["created_at"]} for c in comments],
    })


@app.route("/api/sessions/<int:session_id>/submit", methods=["POST"])
@api_student_required
def api_submit_assignment(session_id):
    conn = g.api_conn
    student = g.api_student
    data = request.get_json(silent=True) or request.form
    content_text = (data.get("content_text") or "").strip()

    s = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if not s:
        return jsonify({"error": "مش موجودة"}), 404

    conn.execute(
        """INSERT INTO submissions (student_id, session_id, sub_type, title, content_text, submitted_at)
           VALUES (?, ?, 'assignment', ?, ?, ?)""",
        (student["id"], session_id, f"Assignment - {s['title']}", content_text,
         datetime.now().strftime("%Y-%m-%d %H:%M"))
    )
    conn.commit()
    return jsonify({"ok": True})


@app.route("/api/sessions/<int:session_id>/comment", methods=["POST"])
@api_student_required
def api_post_comment(session_id):
    conn = g.api_conn
    student = g.api_student
    data = request.get_json(silent=True) or request.form
    text = (data.get("comment_text") or "").strip()
    if not text:
        return jsonify({"error": "اكتب تعليق"}), 400

    conn.execute(
        "INSERT INTO session_comments (session_id, student_id, comment_text, created_at) VALUES (?, ?, ?, ?)",
        (session_id, student["id"], text, datetime.now().strftime("%Y-%m-%d %H:%M"))
    )
    conn.commit()
    return jsonify({"ok": True})


@app.route("/api/leaderboard")
def api_leaderboard():
    conn = get_db()
    rows = conn.execute("""
        SELECT s.full_name, s.track, COALESCE(SUM(p.points), 0) AS total_points
        FROM students s
        LEFT JOIN points_log p ON p.student_id = s.id
        WHERE s.show_on_leaderboard = 1
        GROUP BY s.id ORDER BY total_points DESC LIMIT 20
    """).fetchall()
    conn.close()
    return jsonify([
        {"name": r["full_name"], "track": r["track"], "points": r["total_points"],
         "level": level_for_points(r["total_points"])[0]}
        for r in rows
    ])


@app.route("/api/moments/stories")
@api_student_required
def api_stories():
    conn = g.api_conn
    student = g.api_student
    stories = get_active_stories(conn, student["id"])
    return jsonify(stories)


@app.route("/api/moments/archive")
def api_moments_archive():
    conn = get_db()
    rows = conn.execute("""
        SELECT m.id, m.caption, m.file_path, m.created_at, s.full_name
        FROM moments m JOIN students s ON s.id = m.student_id
        WHERE m.is_approved = 1 ORDER BY m.created_at DESC
    """).fetchall()
    conn.close()
    return jsonify([
        {"id": r["id"], "caption": r["caption"], "file_path": r["file_path"],
         "created_at": r["created_at"], "student_name": r["full_name"]}
        for r in rows
    ])


@app.route("/api/moments/new", methods=["POST"])
@api_student_required
def api_moment_new():
    conn = g.api_conn
    student = g.api_student
    caption = request.form.get("caption", "").strip()
    file = request.files.get("file")

    if not file or not file.filename or not allowed_file(file.filename):
        return jsonify({"error": "لازم صورة أو فيديو بصيغة مدعومة"}), 400

    filename = secure_filename(f"moment_{student['id']}_{secrets.token_hex(4)}_{file.filename}")
    file_path = upload_to_storage(file, filename)

    conn.execute(
        "INSERT INTO moments (student_id, caption, file_path, is_approved, created_at) VALUES (?, ?, ?, 1, ?)",
        (student["id"], caption, file_path, datetime.now().strftime("%Y-%m-%d %H:%M"))
    )
    conn.commit()
    return jsonify({"ok": True, "message": "اترفعت بنجاح"})

@app.route("/api/moments/view/<int:moment_id>", methods=["POST"])
@api_student_required
def api_moment_view(moment_id):
    conn = g.api_conn
    student = g.api_student
    conn.execute(
        "INSERT INTO moment_views (moment_id, viewer_student_id, viewed_at) VALUES (?, ?, ?) ON CONFLICT (moment_id, viewer_student_id) DO NOTHING",
        (moment_id, student["id"], datetime.now().strftime("%Y-%m-%d %H:%M"))
    )
    conn.commit()
    return jsonify({"ok": True})
@app.route("/api/moments/<int:moment_id>/like", methods=["POST"])
@api_student_required
def api_moment_like(moment_id):
    conn = g.api_conn
    student = g.api_student

    already = conn.execute(
        "SELECT 1 FROM moment_likes WHERE moment_id = ? AND student_id = ?",
        (moment_id, student["id"])
    ).fetchone()

    if already:
        conn.execute("DELETE FROM moment_likes WHERE moment_id = ? AND student_id = ?", (moment_id, student["id"]))
        liked = False
    else:
        conn.execute(
            "INSERT INTO moment_likes (moment_id, student_id, liked_at) VALUES (?, ?, ?)",
            (moment_id, student["id"], datetime.now().strftime("%Y-%m-%d %H:%M"))
        )
        liked = True

    conn.commit()
    likes_count = conn.execute("SELECT COUNT(*) AS c FROM moment_likes WHERE moment_id = ?", (moment_id,)).fetchone()["c"]
    return jsonify({"liked": liked, "likes_count": likes_count})

@app.route("/api/sessions/<int:session_id>/rate", methods=["POST"])
@api_student_required
def api_rate_session(session_id):
    conn = g.api_conn
    student = g.api_student
    data = request.get_json(silent=True) or request.form
    try:
        rating = int(data.get("rating"))
    except (TypeError, ValueError):
        return jsonify({"error": "قيمة غير صحيحة"}), 400
    if rating < 1 or rating > 5:
        return jsonify({"error": "التقييم من 1 لـ5"}), 400

    conn.execute("""
        INSERT INTO session_ratings (session_id, student_id, rating, created_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT (session_id, student_id) DO UPDATE SET rating = EXCLUDED.rating, created_at = EXCLUDED.created_at
    """, (session_id, student["id"], rating, datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.commit()
    return jsonify({"ok": True})


@app.route("/api/home")
@api_student_required
def api_home():
    conn = g.api_conn
    best_instructor = get_best_instructor(conn)
    spotlight = get_active_spotlight(conn)
    return jsonify({"best_instructor": best_instructor, "spotlight": spotlight})

@app.route("/api/moments/<int:moment_id>/viewers")
@api_student_required
def api_moment_viewers(moment_id):
    conn = g.api_conn
    student = g.api_student

    moment = conn.execute("SELECT * FROM moments WHERE id = ?", (moment_id,)).fetchone()
    if not moment or moment["student_id"] != student["id"]:
        return jsonify({"error": "دي مش لحظتك"}), 403

    viewers = conn.execute("""
        SELECT v.viewed_at, s.full_name, s.id AS student_id
        FROM moment_views v JOIN students s ON s.id = v.viewer_student_id
        WHERE v.moment_id = ? ORDER BY v.viewed_at DESC
    """, (moment_id,)).fetchall()

    liked_ids = {
        r["student_id"] for r in conn.execute(
            "SELECT student_id FROM moment_likes WHERE moment_id = ?", (moment_id,)
        ).fetchall()
    }

    return jsonify([
        {"name": v["full_name"], "viewed_at": v["viewed_at"], "liked": v["student_id"] in liked_ids}
        for v in viewers
    ])


@app.route("/api/moments/<int:moment_id>/delete", methods=["POST"])
@api_student_required
def api_moment_delete(moment_id):
    conn = g.api_conn
    student = g.api_student

    moment = conn.execute("SELECT * FROM moments WHERE id = ?", (moment_id,)).fetchone()
    if not moment or moment["student_id"] != student["id"]:
        return jsonify({"error": "دي مش لحظتك"}), 403

    conn.execute("DELETE FROM moment_likes WHERE moment_id = ?", (moment_id,))
    conn.execute("DELETE FROM moment_views WHERE moment_id = ?", (moment_id,))
    conn.execute("DELETE FROM moments WHERE id = ?", (moment_id,))
    conn.commit()
    return jsonify({"ok": True})



if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 82))
    app.run(host="0.0.0.0", port=port, debug=True)
