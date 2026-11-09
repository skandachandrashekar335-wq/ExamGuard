import re
from datetime import datetime
from difflib import SequenceMatcher
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.chatbot import ChatQueryLog, KnowledgeBaseItem
from app.schemas.chatbot import (
    ChatCategory,
    ChatCategoryListResponse,
    ChatQueryResponse,
    KnowledgeBaseItemCreate,
    KnowledgeBaseItemUpdate,
)

# Supported categories
CATEGORY_DEFINITIONS: list[dict[str, str]] = [
    {
        "name": "COURSES",
        "title": "Courses & Academic Programs",
        "description": "Undergraduate and postgraduate degrees, branches, curriculum and specializations.",
    },
    {
        "name": "ADMISSIONS",
        "title": "Admission Procedure & Counseling",
        "description": "Application process, entrance quotas (KCET/COMEDK/Management), and enrollment steps.",
    },
    {
        "name": "ELIGIBILITY",
        "title": "Eligibility Criteria",
        "description": "Academic prerequisites, minimum percentages, and entrance exam qualification rules.",
    },
    {
        "name": "FEES",
        "title": "Fee Structure & Payment",
        "description": "Tuition fees, payment modes, official payment channels, and fee confirmation guidelines.",
    },
    {
        "name": "DOCUMENTS",
        "title": "Required Documents",
        "description": "Verification certificates, marks cards, identity proof, and transfer documentation.",
    },
    {
        "name": "EXAMINATIONS",
        "title": "Examinations & Entry Verification",
        "description": "Hall tickets, ExamGuard biometric gates, reporting times, and exam hall rules.",
    },
    {
        "name": "TIMETABLES",
        "title": "Exam & Class Timetables",
        "description": "Academic schedules, mid-term dates, end-semester exam timelines, and notice boards.",
    },
    {
        "name": "FACILITIES",
        "title": "Campus Facilities",
        "description": "Library, computing labs, hostel accommodation, sports complex, and medical services.",
    },
    {
        "name": "GENERAL",
        "title": "General Inquiries & Campus Contacts",
        "description": "Campus working hours, contact info, office locations, and grievance support.",
    },
]

# Grounded institutional knowledge entries for Dayananda Sagar College of Arts, Science and Commerce (DSCASC)
DEFAULT_KNOWLEDGE_BASE: list[dict] = [
    # COURSES
    {
        "category": "COURSES",
        "intent": "courses_undergraduate_list",
        "question": "What undergraduate (UG) courses and programs are offered at DSCASC?",
        "answer": (
            "Dayananda Sagar College of Arts, Science and Commerce (DSCASC) offers the following undergraduate (UG) programs affiliated with Bengaluru City University (BCU): "
            "1) BCA (Bachelor of Computer Applications) - 3-Year / NEP 4-Year Honors degree in software and computing. "
            "2) BBA (Bachelor of Business Administration) - Regular and Aviation Management specializations. "
            "3) B.Com (Bachelor of Commerce) - Regular, Honors, and professional ACCA integrated programs. "
            "4) B.Sc (Bachelor of Science) - Combinations including Computer Science, Electronics, Mathematics, and Life Sciences (Biotechnology/Biochemistry/Genetics). "
            "5) BA (Bachelor of Arts) - Journalism, Psychology, and English Literature. "
            "[Important Institutional Note]: DSCASC specifically offers Arts, Science, Commerce, and Management degrees. "
            "Engineering degrees (B.E. / B.Tech in CSE, ECE, AIML, Mechanical, etc.) are offered separately by sister technical institutions "
            "(Dayananda Sagar College of Engineering - DSCE / Dayananda Sagar University - DSU) on affiliated campuses, not by DSCASC. "
            "[Source: DSCASC Academic Programs Catalog & Bengaluru City University Affiliation Records]"
        ),
        "keywords": "courses, undergraduate, ug programs, bca, bba, bcom, bsc, ba, degrees, degree programs, commerce, science, arts, engineering branches, btech, be, cse, dscasc courses",
        "is_verified": True,
        "requires_admin_confirmation": False,
    },
    {
        "category": "COURSES",
        "intent": "courses_postgraduate_list",
        "question": "What postgraduate (PG) courses are offered at DSCASC?",
        "answer": (
            "Postgraduate (PG) programs offered at Dayananda Sagar College of Arts, Science and Commerce (DSCASC) include: "
            "1) MCA (Master of Computer Applications - 2 Years) - AICTE approved, affiliated with Bengaluru City University (BCU). "
            "2) MBA (Master of Business Administration - 2 Years) - AICTE approved, offering Finance, Marketing, and Human Resource Management specializations. "
            "3) M.Com (Master of Commerce - 2 Years) - Advanced studies in Accounting, Taxation, and Corporate Finance. "
            "4) M.Sc (Biochemistry / Biotechnology - 2 Years) - Specialized research-oriented laboratory degrees. "
            "All PG admissions require a recognized bachelor's degree with valid entrance qualification (such as Karnataka PGCET, KMAT, or institutional test). "
            "[Source: DSCASC Postgraduate Admissions Bulletin & AICTE Approval Order]"
        ),
        "keywords": "pg programs, masters, mca, mba, mcom, msc, master of computer applications, master of business administration, postgraduate degrees, dscasc pg",
        "is_verified": True,
        "requires_admin_confirmation": False,
    },
    # ADMISSIONS
    {
        "category": "ADMISSIONS",
        "intent": "admissions_process_steps",
        "question": "What is the admission procedure for degree programs at DSCASC?",
        "answer": (
            "The admission procedure for Dayananda Sagar College of Arts, Science and Commerce (DSCASC): "
            "1) Application: Submit the completed application form online or in person at the DSCASC Admissions Office. "
            "2) Merit & Counseling: For UG courses (BCA, BBA, B.Com, B.Sc), selection is based on 10+2 / 2nd PUC qualifying marks followed by an admissions interview. "
            "3) Entrance Verification (PG): For MCA and MBA, seats are allotted either through Karnataka PGCET counseling (KEA government quota) or through the institutional Management Quota (valid PGCET / KMAT / CMAT / MAT score). "
            "4) Document Verification: Candidates submit verified original certificates and mark sheets at the campus counter. "
            "5) Fee Payment: Remit prescribed tuition fees through the official college payment channels to confirm enrollment. "
            "6) Admission Clearance: Receive your official admission slip, Student Registration Number / USN, and campus ID card. "
            "[Note: For B.E. / B.Tech engineering admissions via KCET / COMEDK, candidates should apply directly to Dayananda Sagar College of Engineering (DSCE).] "
            "[Source: DSCASC Admissions Office Guidelines & KEA PGCET Information Brochure]"
        ),
        "keywords": "admission process, how to apply, procedure, enrollment, seat allotment, pgcet counseling, kcet counseling, comedk counseling, btech programs, management quota, admission steps, interview, dscasc admission",
        "is_verified": True,
        "requires_admin_confirmation": False,
    },
    {
        "category": "ADMISSIONS",
        "intent": "admissions_contact_office",
        "question": "Where is the Admissions Office located and how can I reach them?",
        "answer": (
            "The Admissions Office is located at: "
            "Dayananda Sagar College of Arts, Science and Commerce (DSCASC), "
            "Administrative Block (Ground Floor), Shavige Malleshwara Hills, Kumaraswamy Layout, Bengaluru, Karnataka - 560111. "
            "Office Timings: Monday through Friday, 9:00 AM to 4:45 PM; Saturday, 9:00 AM to 1:00 PM. "
            "Official Admission Helpline Email: admissions@dscasc.edu.in / admissions@college.edu. "
            "Phone: +91 (080) 2666-2222 / +91 (080) 4216-1704. "
            "[Source: DSCASC Institutional Campus Directory]"
        ),
        "keywords": "admissions office, contact admission, admissions phone, admission email, visit admission block, administrative block, office timing, kumaraswamy layout address, dscasc contact",
        "is_verified": True,
        "requires_admin_confirmation": False,
    },
    # ELIGIBILITY
    {
        "category": "ELIGIBILITY",
        "intent": "eligibility_bca_bba_bcom",
        "question": "What is the eligibility criteria for BCA, BBA, and B.Com admission at DSCASC?",
        "answer": (
            "Undergraduate eligibility criteria at DSCASC (in accordance with Bengaluru City University regulations): "
            "1) BCA: Candidate must have passed 10+2 / 2nd PUC / equivalent examination with a minimum of 40% aggregate marks (pass class for Karnataka SC/ST/Category-1 candidates), preferably with Mathematics, Statistics, Computer Science, Accountancy, or Business Mathematics. "
            "2) BBA: Candidate must have passed 10+2 / 2nd PUC or equivalent in Science, Commerce, or Arts stream with minimum aggregate marks prescribed by the university. "
            "3) B.Com: Candidate must have passed 10+2 / 2nd PUC or equivalent with Commerce, Accountancy, or Science subjects. "
            "4) B.Sc: Candidate must have passed 10+2 / 2nd PUC with relevant Science subjects (Mathematics, Physics, Chemistry, Biology, or Computer Science) with minimum 40% aggregate marks. "
            "[Note on Engineering]: For candidates inquiring about B.E./B.Tech engineering eligibility, minimum 45% in Physics, Mathematics and Chemistry in 10+2 with KCET/COMEDK rank applies at sister engineering college DSCE. "
            "[Source: Bengaluru City University UG Regulations & DSCASC Admission Eligibility Manual]"
        ),
        "keywords": "eligibility bca, eligibility bba, eligibility bcom, eligibility btech, eligibility criteria, minimum marks, 12th percentage, puc cutoff, puc marks, 10+2, 45%, 40%, sc st category reservation, criteria",
        "is_verified": True,
        "requires_admin_confirmation": False,
    },
    {
        "category": "ELIGIBILITY",
        "intent": "eligibility_mca_mba",
        "question": "What is the eligibility for MCA and MBA postgraduate courses at DSCASC?",
        "answer": (
            "Eligibility for DSCASC Postgraduate programs: "
            "1) MCA (2 Years): Recognized Bachelor's degree (such as BCA, B.Sc, B.Com, or B.A.) of minimum 3 years duration with Mathematics at 10+2 level or graduation level. "
            "Candidates must have scored at least 50% aggregate marks (45% for Karnataka SC/ST/Category-1 candidates) and possess a valid score in Karnataka PGCET or KMAT. "
            "2) MBA (2 Years): Recognized Bachelor's degree of minimum 3 years duration with at least 50% aggregate marks (45% for Karnataka SC/ST/Category-1 candidates), along with a valid score in PGCET, KMAT, CMAT, or MAT. "
            "[Source: Karnataka Examinations Authority (KEA) PGCET Guidelines & AICTE Criteria]"
        ),
        "keywords": "eligibility mca, eligibility mba, mca requirements, mba qualifications, pgcet mca cutoff, pgcet mba, kmat cutoff, maths at 12th, graduation percentage",
        "is_verified": True,
        "requires_admin_confirmation": False,
    },
    # FEES
    {
        "category": "FEES",
        "intent": "fees_structure_tuition",
        "question": "What is the fee structure for courses at DSCASC?",
        "answer": (
            "Tuition and examination fees at DSCASC depend on the program and entry quota: "
            "1) Government Quota (PG - MCA / MBA): Tuition fees are regulated according to statutory fees established by the Government of Karnataka / KEA. "
            "2) Management Quota (UG & PG): Prescribed by the DSI Governing Council for BCA, BBA, B.Com, B.Sc, MCA, and MBA based on program and specialization. "
            "3) University Fees: Registration, eligibility, and semester examination fees are remitted as per Bengaluru City University (BCU) mandates. "
            "[ADMINISTRATIVE CONFIRMATION REQUIRED]: Current academic year fee schedules, hostel charges, and lab deposits vary annually. "
            "Students and parents must verify and collect the official, signed fee card directly from the DSCASC Accounts Section or Admissions Counter before remitting payments. "
            "Never pay cash or transfer funds to personal or unverified accounts. "
            "[Source: DSCASC Finance & Accounts Office and KEA Fee Notification]"
        ),
        "keywords": "fee structure, tuition fee, college fees, exam fees, kcet fee, pgcet fee, comedk fee, management fee, bca fee, mba fee, mca fee, payment mode, challan, accounts section",
        "is_verified": True,
        "requires_admin_confirmation": True,
    },
    {
        "category": "FEES",
        "intent": "fees_payment_methods",
        "question": "How can I pay my college tuition and examination fees?",
        "answer": (
            "Approved fee payment channels for DSCASC: "
            "1) Official ERP Student Portal: Secure online payment using Net Banking, UPI, or Debit/Credit Cards. "
            "2) Demand Draft (DD): Drawn in favor of 'Dayananda Sagar College of Arts, Science and Commerce', payable at Bengaluru. "
            "3) Campus Bank Challan: Direct deposit at the designated on-campus Bank of Baroda / bank branch located at the Kumaraswamy Layout campus. "
            "Always retain your printed stamped receipt for audit, semester registration, and exam hall ticket clearance. "
            "[Source: DSCASC Accounts Section Fee Collection Protocol]"
        ),
        "keywords": "how to pay fee, payment methods, upi payment, net banking, demand draft, dd details, bank challan, fee receipt, accounts office",
        "is_verified": True,
        "requires_admin_confirmation": False,
    },
    # DOCUMENTS
    {
        "category": "DOCUMENTS",
        "intent": "documents_required_admission",
        "question": "What original documents are required at the time of admission to DSCASC?",
        "answer": (
            "Candidates must submit the following documents during admission verification: "
            "1) 10th / SSLC Marks Card (proof of date of birth). "
            "2) 12th / 2nd PUC / Equivalent Marks Card. "
            "3) Degree Certificate & Semester Marks Cards (for PG courses: MCA / MBA / M.Com / M.Sc). "
            "4) Transfer Certificate (TC) from the last attended school or college. "
            "5) Migration Certificate (for non-Karnataka students or non-state boards). "
            "6) Study / Character / Conduct Certificate (minimum 7 years in Karnataka for domicile quota benefits). "
            "7) Caste / Income Certificate (if claiming reservation, issued by Tahsildar / Karnataka Revenue Department). "
            "8) Aadhaar Card copy of candidate and parent/guardian. "
            "9) 6 passport-size recent color photographs and 2 stamp-size photographs. "
            "10) PGCET / KMAT Allotment Letter and Rank Card (for government/quota PG applicants). "
            "[Source: DSCASC Admissions Verification Checklist & Bengaluru City University Norms]"
        ),
        "keywords": "documents required, admission documents, certificates needed, 10th marks card, 12th marks card, transfer certificate, tc, migration certificate, caste certificate, study certificate, aadhaar copy, pgcet allotment letter",
        "is_verified": True,
        "requires_admin_confirmation": False,
    },
    # EXAMINATIONS
    {
        "category": "EXAMINATIONS",
        "intent": "exam_entry_hallticket_rules",
        "question": "What are the examination hall rules and hall ticket requirements under ExamGuard?",
        "answer": (
            "Examination Entry & Verification Rules under ExamGuard at DSCASC: "
            "1) Valid Hall Ticket: Every candidate must carry an official, printed hall ticket / admit card bearing their USN / Registration Number and photograph. "
            "2) Biometric Verification: Candidates must pass through the ExamGuard entry checkpoint where camera face verification matches live identity against enrolled records. "
            "3) Reporting Time: Candidates must report to the exam venue at least 30 minutes before the scheduled exam start. "
            "4) Strict Prohibitions: Mobile phones, smartwatches, programmable calculators, electronic devices, study chits, and bags are strictly forbidden inside the exam hall. "
            "5) Secondary Review: If biometric verification requires manual review, the assigned invigilator inspects physical government photo ID before granting authorized access. "
            "[Source: ExamGuard Operations Manual & DSCASC Examination Committee Regulations]"
        ),
        "keywords": "exam rules, hall ticket, admit card, exam entry, face verification, examguard check, invigilator verification, reporting time, prohibited items, electronics, mobile phone in exam",
        "is_verified": True,
        "requires_admin_confirmation": False,
    },
    {
        "category": "EXAMINATIONS",
        "intent": "exam_biometric_face_verification",
        "question": "How does the ExamGuard face verification work on exam day?",
        "answer": (
            "ExamGuard provides AI-powered, contactless identity verification for campus examinations: "
            "1) At the hall entrance, the candidate's USN is entered or scanned by the invigilator. "
            "2) The candidate faces the live camera for a rapid 2-second capture. "
            "3) The system matches live facial geometry with the enrolled reference portrait using UniFace deep embeddings. "
            "4) MATCH: Immediately authorizes entry and stamps verifiable attendance. "
            "5) INCONCLUSIVE / REVIEW: Invigilator inspects physical identity and enters a logged justification. "
            "6) NO_MATCH: Entry is blocked to prevent proxy attendance and impersonation fraud. "
            "[Source: ExamGuard Biometric Perception Architecture & UniFace Engine]"
        ),
        "keywords": "examguard, how face verification works, live camera check, match, no match, biometric attendance, impersonation prevention, uniface",
        "is_verified": True,
        "requires_admin_confirmation": False,
    },
    # TIMETABLES
    {
        "category": "TIMETABLES",
        "intent": "timetables_exam_schedule",
        "question": "Where can I view the exam timetables and academic calendar?",
        "answer": (
            "Exam timetables and academic schedules are published through: "
            "1) DSCASC Official Departmental and Central Notice Boards. "
            "2) Student ERP Portal under the 'Examinations & Timetables' module. "
            "3) Bengaluru City University (BCU) Examination Portal for university semester examinations. "
            "End-semester examination timetables are typically released 3 to 4 weeks prior to the examination start date. "
            "Internal Assessment (IA) test dates are scheduled by respective department heads at the start of each semester. "
            "[Source: DSCASC Controller of Examinations & BCU Academic Calendar]"
        ),
        "keywords": "timetables, exam schedule, academic calendar, when are exams, test dates, internal assessment schedule, exam dates, notice board, bcu timetable",
        "is_verified": True,
        "requires_admin_confirmation": False,
    },
    # FACILITIES
    {
        "category": "FACILITIES",
        "intent": "facilities_campus_overview",
        "question": "What campus facilities and amenities are available for students at DSCASC?",
        "answer": (
            "Campus amenities at the Kumaraswamy Layout campus: "
            "1) Central Library: Comprehensive collection of over 40,000 textbooks, reference volumes, DELNET e-resources, national/international journals, and digital browsing center. "
            "2) Computing Labs: Modern high-performance computer laboratories with high-speed internet and development environments for BCA and MCA students. "
            "3) Hostel Accommodation: Separate well-secured hostels for male and female students with Wi-Fi, 24/7 security, and hygienic dining mess. "
            "4) Sports & Recreation: Indoor badminton courts, basketball and volleyball grounds, athletic track, and fully equipped gymnasium. "
            "5) Health Center: On-campus medical clinic with resident nursing staff and emergency ambulance facility. "
            "6) Food Court & Cafeteria: Multi-cuisine hygienic cafeterias and student dining centers. "
            "[Source: DSCASC Campus Infrastructure Handbook & DSI Facilities Guide]"
        ),
        "keywords": "facilities, campus amenities, library, computer labs, hostel, boys hostel, girls hostel, sports, gym, medical center, cafeteria, mess food, kumaraswamy layout campus",
        "is_verified": True,
        "requires_admin_confirmation": False,
    },
    # GENERAL
    {
        "category": "GENERAL",
        "intent": "general_campus_contact",
        "question": "What are the general campus working hours and contact information for DSCASC?",
        "answer": (
            "General Campus Information: "
            "Institution: Dayananda Sagar College of Arts, Science and Commerce (DSCASC). "
            "Campus Address: Shavige Malleshwara Hills, Kumaraswamy Layout, Bengaluru, Karnataka, India - 560111. "
            "Working Hours: Monday to Friday: 8:45 AM - 4:45 PM; Saturday: 8:45 AM - 1:00 PM (Closed on Sundays and Government Holidays). "
            "General Enquiries: info@dscasc.edu.in | Phone: +91 (080) 2666-2222 / +91 (080) 4216-1704. "
            "Admissions Helpline: admissions@dscasc.edu.in / admissions@college.edu. "
            "Student Support & Grievance Cell: grievances@dscasc.edu.in. "
            "ExamGuard Technical Helpdesk: examguard-support@dscasc.edu.in. "
            "[Source: DSCASC Institutional Directory & Contact Registry]"
        ),
        "keywords": "working hours, college timings, address, location, general contact, email, phone number, grievance cell, helpline, bangalore, dscasc, kumaraswamy layout",
        "is_verified": True,
        "requires_admin_confirmation": False,
    },
]

# Popular quick suggestion questions across key categories
SUGGESTED_QUESTIONS: list[str] = [
    "What undergraduate degree courses (BCA, BBA, B.Com, B.Sc) are offered?",
    "What postgraduate programs (MCA, MBA, M.Com) are available?",
    "What is the admission procedure for degree programs?",
    "What are the eligibility criteria for BCA, BBA, and B.Com?",
    "What documents are required at the time of admission?",
    "What is the fee structure and how can I pay?",
    "What are the exam hall rules and hall ticket requirements under ExamGuard?",
    "How does the ExamGuard biometric face verification work on exam day?",
    "Where can I find the exam timetables and academic calendar?",
    "What campus facilities and student amenities are available?",
]

FALLBACK_RESPONSE = (
    "I'm sorry, but I don't have verified institutional information matching your specific query for "
    "Dayananda Sagar College of Arts, Science and Commerce (DSCASC). "
    "To ensure you receive accurate and up-to-date guidance, please contact the "
    "Admissions & Academic Office directly at admissions@dscasc.edu.in / admissions@college.edu or call +91 (080) 2666-2222. "
    "You can also ask me about DSCASC courses (BCA, BBA, B.Com, B.Sc, MCA, MBA), admission procedure, "
    "eligibility criteria, fee guidelines, required documents, ExamGuard biometric exam rules, or campus facilities."
)


STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "to", "at", "in", "for",
    "on", "by", "with", "about", "against", "between", "into", "through",
    "during", "before", "after", "above", "below", "from", "up", "down",
    "of", "off", "over", "under", "again", "further", "then", "once",
    "here", "there", "when", "where", "why", "how", "all", "any", "both",
    "each", "few", "more", "most", "other", "some", "such", "no", "nor",
    "not", "only", "own", "same", "so", "than", "too", "very",
    "can", "will", "just", "should", "now", "i", "me", "my",
    "we", "our", "you", "your", "he", "him", "his", "she", "her", "it",
    "its", "they", "them", "their", "what", "which", "who", "whom", "this",
    "that", "these", "those", "am", "tell", "please", "give"
}


def normalize_text(text: str) -> str:
    """Normalize text by lowercasing and stripping non-alphanumeric punctuation."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def calculate_similarity(query_tokens: set[str], doc_tokens: set[str], full_query: str, full_target: str) -> float:
    """
    Compute multi-tier similarity between normalized query and candidate entry.
    Combines Jaccard token overlap with SequenceMatcher ratio for robust fuzzy matching.
    """
    if not query_tokens or not doc_tokens:
        return 0.0

    content_query = query_tokens - STOPWORDS
    effective_query = content_query if content_query else query_tokens

    # 1. Token overlap (Jaccard similarity on effective tokens)
    intersection = len(effective_query & doc_tokens)
    union = len(effective_query | doc_tokens)
    token_score = intersection / union if union > 0 else 0.0

    # 2. Sequence matcher ratio on normalized strings
    char_ratio = SequenceMatcher(None, full_query, full_target).ratio()

    # 3. Substring containment boost
    substring_boost = 0.0
    if len(full_query) >= 4 and (full_query in full_target or full_target in full_query):
        substring_boost = 0.35

    # 4. Content token hit ratio (what percentage of query content words appear in doc)
    query_hit_ratio = intersection / len(effective_query) if effective_query else 0.0

    # Weighted composite score
    combined = (token_score * 0.20) + (query_hit_ratio * 0.45) + (char_ratio * 0.15) + (substring_boost * 0.20)
    return min(1.0, combined)


def seed_knowledge_base_if_empty(db: Session) -> int:
    """Seed the database with default grounded knowledge items if empty."""
    count = db.query(KnowledgeBaseItem).count()
    if count > 0:
        return count

    for item_data in DEFAULT_KNOWLEDGE_BASE:
        item = KnowledgeBaseItem(
            category=item_data["category"],
            intent=item_data["intent"],
            question=item_data["question"],
            answer=item_data["answer"],
            keywords=item_data["keywords"],
            is_verified=item_data.get("is_verified", True),
            requires_admin_confirmation=item_data.get("requires_admin_confirmation", False),
            is_active=True,
        )
        db.add(item)
    db.commit()
    return len(DEFAULT_KNOWLEDGE_BASE)


def get_all_active_knowledge(db: Session) -> list[dict]:
    """Retrieve all active knowledge items from DB, falling back to DEFAULT_KNOWLEDGE_BASE."""
    items = db.query(KnowledgeBaseItem).filter(KnowledgeBaseItem.is_active == True).all()
    if items:
        return [
            {
                "id": it.id,
                "category": it.category,
                "intent": it.intent,
                "question": it.question,
                "answer": it.answer,
                "keywords": it.keywords,
                "is_verified": it.is_verified,
                "requires_admin_confirmation": it.requires_admin_confirmation,
            }
            for it in items
        ]
    return DEFAULT_KNOWLEDGE_BASE


def match_intent(query: str, knowledge_items: list[dict]) -> tuple[dict | None, float]:
    """
    Match natural-language query to the best knowledge base item.
    Returns (matched_item, confidence_score).
    """
    clean_query = normalize_text(query)
    query_tokens = set(clean_query.split())

    if not query_tokens:
        return None, 0.0

    best_item: dict | None = None
    best_score: float = 0.0

    content_tokens = query_tokens - STOPWORDS
    effective_query = content_tokens if content_tokens else query_tokens

    for item in knowledge_items:
        clean_question = normalize_text(item["question"])
        clean_keywords = normalize_text(item.get("keywords", ""))
        clean_intent = normalize_text(item["intent"].replace("_", " "))

        target_text = f"{clean_question} {clean_keywords} {clean_intent}"
        target_tokens = set(target_text.split())

        # Direct question similarity
        q_score = calculate_similarity(query_tokens, set(clean_question.split()), clean_query, clean_question)

        # Keyword matching score using effective query tokens
        kw_tokens = set(clean_keywords.split())
        kw_intersection = len(effective_query & kw_tokens)
        kw_score = (kw_intersection / len(effective_query)) if effective_query else 0.0

        # Composite score for this knowledge item
        item_score = max(q_score, (kw_score * 0.75 + q_score * 0.25))

        # Direct category boost if category name appears in query
        if item["category"].lower() in query_tokens:
            item_score = min(1.0, item_score + 0.15)

        if item_score > best_score:
            best_score = item_score
            best_item = item

    return best_item, best_score


def get_contextual_suggestions(category: str | None = None) -> list[str]:
    """Return top 3-4 suggested questions relevant to the query category."""
    if not category:
        return SUGGESTED_QUESTIONS[:4]

    category_questions = [
        item["question"]
        for item in DEFAULT_KNOWLEDGE_BASE
        if item["category"].upper() == category.upper()
    ]
    if category_questions:
        return category_questions[:3]
    return SUGGESTED_QUESTIONS[:3]


def process_chat_query(
    db: Session,
    query: str,
    session_id: str | None = None,
) -> ChatQueryResponse:
    """
    Public student chatbot query processor.
    1. Retrieves knowledge base.
    2. Matches query against intent catalog using multi-tier similarity.
    3. Returns grounded response or honest fallback with related topics.
    4. Logs query in ChatQueryLog for quality auditing.
    """
    clean_query = query.strip()
    knowledge_items = get_all_active_knowledge(db)
    matched_item, confidence = match_intent(clean_query, knowledge_items)

    MATCH_THRESHOLD = 0.38

    if matched_item and confidence >= MATCH_THRESHOLD:
        answer = matched_item["answer"]
        category = matched_item["category"]
        intent = matched_item["intent"]
        requires_admin = matched_item.get("requires_admin_confirmation", False)
        is_verified = matched_item.get("is_verified", True)
        is_matched = True
        suggestions = get_contextual_suggestions(category)
    else:
        answer = FALLBACK_RESPONSE
        category = "GENERAL"
        intent = "fallback_unknown_intent"
        requires_admin = True
        is_verified = False
        is_matched = False
        suggestions = SUGGESTED_QUESTIONS[:4]

    # Log to audit history in DB
    try:
        log_entry = ChatQueryLog(
            session_id=session_id,
            query_text=clean_query[:500],
            matched_intent=intent,
            category=category,
            confidence=round(confidence, 4),
            response_text=answer,
        )
        db.add(log_entry)
        db.commit()
    except Exception:
        db.rollback()

    return ChatQueryResponse(
        query=clean_query,
        answer=answer,
        category=category,
        intent=intent,
        confidence=round(confidence, 4),
        matched=is_matched,
        suggestions=suggestions,
        requires_admin_confirmation=requires_admin,
        is_verified=is_verified,
    )


def list_categories() -> ChatCategoryListResponse:
    """Return all supported categories with descriptions and sample queries."""
    result = []
    for cat in CATEGORY_DEFINITIONS:
        sample_qs = [
            item["question"]
            for item in DEFAULT_KNOWLEDGE_BASE
            if item["category"] == cat["name"]
        ]
        result.append(
            ChatCategory(
                name=cat["name"],
                title=cat["title"],
                description=cat["description"],
                sample_questions=sample_qs[:2],
            )
        )
    return ChatCategoryListResponse(categories=result)


# Admin CRUD operations for knowledge base management
def create_knowledge_item(db: Session, data: KnowledgeBaseItemCreate) -> KnowledgeBaseItem:
    existing = db.query(KnowledgeBaseItem).filter(KnowledgeBaseItem.intent == data.intent.strip()).first()
    if existing:
        raise ValueError(f"Knowledge item with intent '{data.intent}' already exists")

    item = KnowledgeBaseItem(
        category=data.category.upper(),
        intent=data.intent.strip(),
        question=data.question.strip(),
        answer=data.answer.strip(),
        keywords=data.keywords.strip(),
        is_verified=data.is_verified,
        requires_admin_confirmation=data.requires_admin_confirmation,
        is_active=True,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def get_knowledge_item(db: Session, item_id: int) -> KnowledgeBaseItem | None:
    return db.query(KnowledgeBaseItem).filter(KnowledgeBaseItem.id == item_id).first()


def list_knowledge_items(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    category: str | None = None,
    search: str | None = None,
    include_inactive: bool = False,
) -> tuple[list[KnowledgeBaseItem], int]:
    seed_knowledge_base_if_empty(db)
    query = db.query(KnowledgeBaseItem)

    if not include_inactive:
        query = query.filter(KnowledgeBaseItem.is_active == True)

    if category:
        query = query.filter(KnowledgeBaseItem.category == category.upper())

    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                KnowledgeBaseItem.question.ilike(pattern),
                KnowledgeBaseItem.answer.ilike(pattern),
                KnowledgeBaseItem.keywords.ilike(pattern),
            )
        )

    total = query.count()
    items = (
        query.order_by(KnowledgeBaseItem.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def update_knowledge_item(db: Session, item_id: int, data: KnowledgeBaseItemUpdate) -> KnowledgeBaseItem:
    item = db.query(KnowledgeBaseItem).filter(KnowledgeBaseItem.id == item_id).first()
    if not item:
        raise LookupError(f"Knowledge item {item_id} not found")

    update_data = data.model_dump(exclude_unset=True)
    if "intent" in update_data and update_data["intent"]:
        new_intent = update_data["intent"].strip()
        if new_intent != item.intent:
            existing = db.query(KnowledgeBaseItem).filter(KnowledgeBaseItem.intent == new_intent).first()
            if existing:
                raise ValueError(f"Knowledge item with intent '{new_intent}' already exists")
            update_data["intent"] = new_intent

    if "category" in update_data and update_data["category"]:
        update_data["category"] = update_data["category"].upper()

    for k, v in update_data.items():
        if isinstance(v, str):
            v = v.strip()
        setattr(item, k, v)

    db.commit()
    db.refresh(item)
    return item


def deactivate_knowledge_item(db: Session, item_id: int) -> KnowledgeBaseItem:
    item = db.query(KnowledgeBaseItem).filter(KnowledgeBaseItem.id == item_id).first()
    if not item:
        raise LookupError(f"Knowledge item {item_id} not found")

    item.is_active = False
    db.commit()
    db.refresh(item)
    return item
