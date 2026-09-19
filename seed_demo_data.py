"""
سكريبت تعبئة بيانات تجريبية واقعية - يشتغل مرة واحدة على قاعدة بيانات فاضية أو موجودة.
شغّله بالأمر: python seed_demo_data.py
"""
import app as a
from datetime import datetime

a.init_db()
conn = a.get_db()

print("جاري إضافة الطلاب...")

demo_students = [
    ("أحمد سامي عبدالله", "كلية الزراعة", "بيوتكنولوجي", "الثالثة", "01011111101", "Biotechnology"),
    ("مريم حسن فتحي", "كلية الزراعة", "بيوتكنولوجي", "الثالثة", "01011111102", "Biotechnology"),
    ("محمود عبدالرحمن", "كلية الزراعة", "علوم أغذية", "الرابعة", "01011111103", "Food Science"),
    ("سارة إبراهيم علي", "كلية الزراعة", "علوم أغذية", "الثانية", "01011111104", "Food Science"),
    ("يوسف محمد عزت", "كلية الزراعة", "ميكروبيولوجي", "الثالثة", "01011111105", "Microbiology"),
    ("نور الدين طارق", "كلية الزراعة", "أراضي ومياه", "الرابعة", "01011111106", "Soil"),
    ("هبة الله كمال", "كلية الزراعة", "إنتاج حيواني", "الثانية", "01011111107", "Animal Production"),
    ("عمر خالد رشدي", "كلية الزراعة", "إنتاج نباتي", "الثالثة", "01011111108", "Plant"),
    ("فاطمة الزهراء أحمد", "كلية الزراعة", "بيوتكنولوجي", "الثانية", "01011111109", "Biotechnology"),
    ("كريم وليد سعيد", "كلية الهندسة", "حاسبات وأنظمة", "الثالثة", "01011111110", "Biotechnology"),
    ("رنا عصام فوزي", "كلية التجارة", "إدارة أعمال", "الرابعة", "01011111111", "Food Science"),
    ("زياد أشرف نبيل", "كلية العلوم", "كيمياء", "الثانية", "01011111112", "Microbiology"),
    ("ياسمين عادل حلمي", "كلية الآداب", "لغة إنجليزية", "الثالثة", "01011111113", None),
    ("عبدالله رأفت", "كلية الزراعة", "علوم أغذية", "الرابعة", "01011111114", "Food Science"),
    ("دينا محسن يوسف", "كلية الزراعة", "بيوتكنولوجي", "الأولى", "01011111115", "Biotechnology"),
    ("طه إسماعيل بدر", "كلية الزراعة", "أراضي ومياه", "الثالثة", "01011111116", "Soil"),
    ("جنى شريف عاطف", "كلية الزراعة", "إنتاج نباتي", "الثانية", "01011111117", "Plant"),
    ("مصطفى جمال الدين", "كلية الزراعة", "إنتاج حيواني", "الرابعة", "01011111118", "Animal Production"),
    ("ملك حازم فتحي", "كلية التربية", "علوم", "الثالثة", "01011111119", None),
    ("آدم منير صبري", "كلية الزراعة", "ميكروبيولوجي", "الثانية", "01011111120", "Microbiology"),
]

student_ids = []
for name, college, spec, level, phone, track in demo_students:
    existing = conn.execute("SELECT id FROM students WHERE phone = ?", (phone,)).fetchone()
    if existing:
        student_ids.append(existing["id"])
        continue
    email = f"{phone}@demo-student.test"
    code = a.generate_access_code()
    conn.execute(
        """INSERT INTO students (full_name, college, specialization, level, phone, whatsapp, email, track, notes, access_code, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, '', ?, ?)""",
        (name, college, spec, level, phone, phone, email, track, code, datetime.now().strftime("%Y-%m-%d %H:%M"))
    )
    student_ids.append(conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])

conn.commit()
print(f"تمت إضافة {len(student_ids)} طالب")

print("جاري إضافة السيشنز...")

demo_sessions = [
    # module 1
    (1, "Orientation Day", "2026-10-04", "أ.د. هالة منصور", "اليوم التعريفي بالبرنامج والمديولات الستة",
     "https://drive.google.com/placeholder-orientation", None,
     "اكتب فقرة قصيرة عن هدفك الشخصي من الالتحاق بالبرنامج"),
    (1, "LinkedIn Profile Workshop", "2026-10-06", "م. كريم عادل", "بناء بروفايل احترافي على لينكدإن",
     "https://drive.google.com/placeholder-linkedin", "/materials/linkedin_checklist.pdf",
     "ابعت لينك بروفايلك على لينكدإن بعد التعديل"),
    (1, "CV Writing Workshop", "2026-10-11", "أ. سلمى توفيق", "كتابة سيرة ذاتية احترافية من الصفر",
     "https://drive.google.com/placeholder-cv", "/materials/cv_writing_guide.pdf",
     "ارفع نسخة من سيرتك الذاتية بعد التطوير"),
    (1, "Communication & Email Etiquette", "2026-10-13", "د. مايكل فايز", "أساسيات التواصل المهني وكتابة الإيميلات",
     "https://drive.google.com/placeholder-comm", None, "اكتب نموذج إيميل تعارف مهني لجهة عمل"),

    # module 2
    (2, "AI Tools for Productivity", "2026-10-20", "م. عبدالرحمن ناصر", "استخدام أدوات الذكاء الاصطناعي في الدراسة والعمل",
     "https://drive.google.com/placeholder-ai", None, "اكتب 3 استخدامات عملية لأدوات AI في تخصصك"),
    (2, "Excel Essentials", "2026-10-25", "أ. نهى السيد", "أساسيات إكسل للتحليل والتقارير",
     "https://drive.google.com/placeholder-excel", None, "ارفع ملف إكسل فيه جدول بسيط بمعادلة SUM"),
    (2, "Google Workspace & Canva", "2026-10-27", "أ. ياسمين رمزي", "العمل التعاوني والتصميم البسيط",
     "https://drive.google.com/placeholder-canva", None, "صمم بوستر بسيط على Canva وارفعه"),

    # module 3
    (3, "Scientific Research Basics", "2026-11-03", "أ.د. محمد الشربيني", "أساسيات البحث العلمي ومصادره",
     "https://drive.google.com/placeholder-research", "/materials/research_basics_handout.pdf",
     "دوّر على ورقة بحثية متعلقة بتخصصك على Google Scholar ولخصها في 5 أسطر"),
    (3, "Reference Management (Zotero/Mendeley)", "2026-11-08", "د. إيمان جابر", "تنظيم المراجع العلمية",
     "https://drive.google.com/placeholder-zotero", None, "اعمل مكتبة Zotero فيها 5 مراجع في مجالك"),
    (3, "Presentation Skills", "2026-11-10", "أ. حسام الدين طه", "مهارات العرض والتقديم",
     "https://drive.google.com/placeholder-presentation", None, "سجّل فيديو قصير (دقيقتين) تقدم فيه نفسك ومشروعك"),

    # module 4 - practical, split by track
    (4, "PCR & DNA Extraction", "2026-12-01", "د. رامي فوزي", "تجربة عملية في استخلاص الحمض النووي وتفاعل PCR",
     "https://drive.google.com/placeholder-pcr", "/materials/pcr_protocol_handout.pdf",
     "اكتب تقرير مختصر عن خطوات التجربة والنتائج"),
    (4, "Food Analysis & HACCP", "2026-12-03", "د. نيفين عبدالعزيز", "تحليل جودة الأغذية ونظام HACCP",
     "https://drive.google.com/placeholder-haccp", None, "حلل عينة غذائية وهمية حسب معايير HACCP"),
    (4, "Microbiology Lab (Gram Stain)", "2026-12-06", "د. أشرف حلمي", "تجربة صبغة الجرام والزرع الميكروبي",
     "https://drive.google.com/placeholder-gram", None, "وثّق نتيجة تجربة صبغة الجرام بالصور"),
    (4, "Soil Analysis Workshop", "2026-12-08", "د. سامح عبدالوهاب", "تحليل خواص التربة (pH, EC)",
     "https://drive.google.com/placeholder-soil", None, "قيس عينة تربة وسجل النتائج"),
    (4, "Hydroponics & Grafting", "2026-12-10", "م. رشا كامل", "الزراعة المائية والتطعيم",
     "https://drive.google.com/placeholder-hydro", None, "وثّق تجربة تطعيم أو زراعة مائية بسيطة"),

    # module 5
    (5, "Food Company Visit", "2026-12-15", "فريق PR", "زيارة ميدانية لشركة أغذية",
     "https://drive.google.com/placeholder-visit1", None, "اكتب أهم 3 حاجات اتعلمتها من الزيارة"),
    (5, "HR Session - Career Paths", "2026-12-18", "أ. رنا الديب - HR Manager", "جلسة مع مسؤول HR عن سوق العمل",
     "https://drive.google.com/placeholder-hr", None, None),

    # module 6
    (6, "Interview Skills Workshop", "2027-01-05", "أ. عمرو نصر", "التحضير للمقابلات الشخصية",
     "https://drive.google.com/placeholder-interview", None, "اعمل محاكاة مقابلة مع زميل ووثّق ملاحظاتك"),
    (6, "Scholarships & Career Planning", "2027-01-10", "د. لمياء شوقي", "التخطيط لما بعد التخرج والمنح الدراسية",
     "https://drive.google.com/placeholder-scholarships", None, "اكتب خطتك المبدئية لأول سنتين بعد التخرج"),
]

session_ids = []
for module_number, title, date, instructor, desc, rec_url, mat_url, assignment in demo_sessions:
    existing = conn.execute("SELECT id FROM sessions WHERE title = ?", (title,)).fetchone()
    if existing:
        session_ids.append(existing["id"])
        continue
    conn.execute(
        """INSERT INTO sessions (module_number, title, session_date, instructor, description, recording_url, material_url, assignment_text, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (module_number, title, date, instructor, desc, rec_url, mat_url, assignment,
         datetime.now().strftime("%Y-%m-%d %H:%M"))
    )
    session_ids.append(conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])

conn.commit()
print(f"تمت إضافة {len(session_ids)} سيشن")

print("جاري إضافة الفرق...")
demo_teams = ["فريق الأمل", "فريق الريادة", "فريق الابتكار"]
team_ids = []
for name in demo_teams:
    existing = conn.execute("SELECT id FROM teams WHERE name = ?", (name,)).fetchone()
    if existing:
        team_ids.append(existing["id"])
        continue
    conn.execute("INSERT INTO teams (name, created_at) VALUES (?, ?)",
                 (name, datetime.now().strftime("%Y-%m-%d %H:%M")))
    team_ids.append(conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])
conn.commit()

# وزع الطلاب على الفرق
for i, sid in enumerate(student_ids):
    team_id = team_ids[i % len(team_ids)]
    conn.execute("UPDATE students SET team_id = ? WHERE id = ?", (team_id, sid))
conn.commit()
print(f"تمت إضافة {len(team_ids)} فريق وتوزيع الطلاب عليهم")

print("جاري تسجيل نقاط تجريبية...")
import random
random.seed(42)
activities = list(a.ACTIVITY_POINTS.items())
for sid in student_ids:
    num_entries = random.randint(2, 6)
    for _ in range(num_entries):
        activity, points = random.choice(activities)
        conn.execute(
            "INSERT INTO points_log (student_id, activity, points, created_at) VALUES (?, ?, ?, ?)",
            (sid, activity, points, datetime.now().strftime("%Y-%m-%d %H:%M"))
        )
conn.commit()

for sid in student_ids:
    a.check_and_award_badges(conn, sid)

print("تم تسجيل النقاط والبادجات التلقائية")

print("جاري إضافة تسليمات وتوثيقات تجريبية...")
sample_assignment_sessions = [s for s in session_ids][:3]
for sid in student_ids[:8]:
    for sess_id in sample_assignment_sessions:
        conn.execute(
            """INSERT INTO submissions (student_id, session_id, sub_type, title, content_text, points_awarded, submitted_at)
               VALUES (?, ?, 'assignment', 'Assignment submission', 'تسليم تجريبي للـ Assignment', 10, ?)""",
            (sid, sess_id, datetime.now().strftime("%Y-%m-%d %H:%M"))
        )

conn.execute(
    """INSERT INTO submissions (student_id, session_id, sub_type, title, content_text, points_awarded, submitted_at)
       VALUES (?, NULL, 'زيارة', 'زيارة شركة الأغذية المصرية', 'زيارة موفقة اتعرفنا فيها على خطوط الإنتاج', 15, ?)""",
    (student_ids[0], datetime.now().strftime("%Y-%m-%d %H:%M"))
)
conn.execute(
    """INSERT INTO submissions (student_id, session_id, sub_type, title, content_text, points_awarded, submitted_at)
       VALUES (?, NULL, 'ورقة بحثية', 'ملخص بحث عن تقنيات PCR الحديثة', 'قراءة وتلخيص ورقة علمية عن qPCR', 20, ?)""",
    (student_ids[1], datetime.now().strftime("%Y-%m-%d %H:%M"))
)
conn.commit()
print("تمت إضافة تسليمات وتوثيقات تجريبية")

print("جاري إضافة تعليقات تجريبية...")
sample_comments = [
    (session_ids[1], student_ids[0], "هل ينفع نستخدم صورة بروفايل بدون بدلة رسمية؟"),
    (session_ids[1], student_ids[2], "أنا لسه معنديش خبرات أحطها، أعمل إيه؟"),
    (session_ids[10], student_ids[3], "هل التجربة هتتعاد لو حد اتأخر؟"),
]
for sess_id, sid, text in sample_comments:
    conn.execute(
        "INSERT INTO session_comments (session_id, student_id, comment_text, created_at) VALUES (?, ?, ?, ?)",
        (sess_id, sid, text, datetime.now().strftime("%Y-%m-%d %H:%M"))
    )
conn.commit()
print("تمت إضافة التعليقات")

conn.close()
print("\n✅ خلصت تعبئة البيانات التجريبية بنجاح!")
print("سجل دخول كأدمن بالباسورد الافتراضية وشوف لوحة التحكم والسيشنز والطلاب.")
