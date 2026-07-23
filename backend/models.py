import uuid
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, JSON, Float, ForeignKey
from database import Base, CABase


class ActivityLog(Base):
    __tablename__ = "activity_log"

    log_id = Column(Integer, primary_key=True, autoincrement=True)
    source_pdf = Column(String, nullable=False)
    stage = Column(String, default="uploaded")
    progress = Column(String, nullable=True)
    status = Column(String, default="in_progress")
    error = Column(Text, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class QuestionAnalysis(Base):
    __tablename__ = "question_analysis"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_pdf = Column(String, nullable=False)
    question_number = Column(Integer, nullable=True)
    question_text = Column(Text, nullable=False)
    options = Column(JSON, nullable=False)
    correct_key = Column(String(1), nullable=False)
    verified_answer = Column(String(1), nullable=True)
    gemini_correct = Column(Boolean, nullable=True)
    trap_type = Column(String, nullable=True)
    trap_mechanism = Column(Text, nullable=True)
    distraction_analysis = Column(JSON, nullable=True)
    most_likely_wrong = Column(String(1), nullable=True)
    most_likely_wrong_reason = Column(Text, nullable=True)
    related_concepts = Column(JSON, nullable=True)
    difficulty_tier = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class StudentProfile(Base):
    __tablename__ = "student_profile"

    student_id = Column(String, primary_key=True)
    name = Column(String, default="Student")
    age = Column(Integer, nullable=True)
    gender = Column(String, nullable=True)
    current_elo = Column(Integer, default=1200)
    subject_elos = Column(JSON, default=dict)
    total_attempted = Column(Integer, default=0)
    total_correct = Column(Integer, default=0)
    trap_stats = Column(JSON, default=dict)
    subject_trap_accuracy = Column(JSON, default=dict)
    weakness_tags = Column(JSON, default=list)
    diagnostic_completed = Column(Boolean, default=False)
    onboarding_complete = Column(Boolean, default=False)
    last_diagnostic_at = Column(DateTime, nullable=True)
    per_subject_accuracy = Column(JSON, default=dict)
    last_active = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)


class TestSession(Base):
    __tablename__ = "test_session"

    session_id = Column(String, primary_key=True)
    subject_code = Column(String, nullable=True)
    topic_studied = Column(String, nullable=False)
    questions = Column(JSON, nullable=False)
    answer_key = Column(JSON, nullable=False)
    responses = Column(JSON, default={})
    score = Column(Integer, nullable=True)
    status = Column(String, default="in_progress")
    pdf_path = Column(String, nullable=True)
    answer_key_path = Column(String, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow)


class AttemptHistory(Base):
    __tablename__ = "attempt_history"

    attempt_id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, nullable=False)
    question_index = Column(Integer, nullable=False)
    response = Column(String(1), nullable=False)
    correct = Column(Boolean, nullable=False)
    time_taken = Column(Integer, nullable=True)
    trap_type = Column(String, nullable=True)
    attempted_at = Column(DateTime, default=datetime.utcnow)


class DiagnosticQuestions(Base):
    __tablename__ = "diagnostic_questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    question_text = Column(Text, nullable=False)
    options = Column(JSON, nullable=False)
    correct_key = Column(String(1), nullable=False)
    subject = Column(String, nullable=False)
    difficulty_tier = Column(Integer, default=5)
    trap_type = Column(String, nullable=True)
    source = Column(String, nullable=False)  # "pyq" or "generated"
    ca_reference = Column(Text, nullable=True)
    ca_sub_topic = Column(String, nullable=True)
    question_type = Column(String, nullable=True)  # direct, twisted_multi, assertion_reason, static_linked
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class DiagnosticResults(Base):
    __tablename__ = "diagnostic_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String, ForeignKey("student_profile.student_id"))
    session_id = Column(String, nullable=False)
    question_ids = Column(JSON, default=list)
    responses = Column(JSON, default=dict)
    score = Column(Integer, nullable=False)
    total = Column(Integer, nullable=False)
    per_subject = Column(JSON, default=dict)
    pdf_path = Column(String, nullable=True)
    answer_key_path = Column(String, nullable=True)
    started_at = Column(DateTime, nullable=True)
    time_taken = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ProfileAnalysis(Base):
    __tablename__ = "profile_analysis"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String, ForeignKey("student_profile.student_id"))
    structured_data = Column(Text)
    coach_report = Column(Text)
    trigger_type = Column(String)  # "scheduled" / "manual"
    question_count_at_analysis = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)


class QuestionTopics(Base):
    __tablename__ = "question_topics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    question_analysis_id = Column(Integer, ForeignKey("question_analysis.id"))
    topic = Column(String)
    subtopic = Column(String)
    confidence = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)


class CurrentAffairs(CABase):
    __tablename__ = "current_affairs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(Text, nullable=False)
    source = Column(String)
    source_url = Column(String, unique=True)
    full_text = Column(Text)
    summary = Column(Text)
    category = Column(String)
    subject = Column(String)
    tags = Column(Text)
    key_facts = Column(Text)
    historical_context = Column(Text)
    upsc_relevance = Column(String)
    image_url = Column(String)
    image_path = Column(String)
    date_of_event = Column(String)
    is_editorial = Column(Boolean, default=False)
    newspaper_name = Column(String)
    date_fetched = Column(String, default=lambda: str(datetime.utcnow().date()))
    created_at = Column(DateTime, default=datetime.utcnow)


class CuratedCA(CABase):
    __tablename__ = "curated_ca"

    id = Column(Integer, primary_key=True, autoincrement=True)
    issue_id = Column(String, index=True, nullable=False)
    title = Column(Text, nullable=False)
    source_url = Column(String, unique=True, nullable=False)
    source = Column(String)
    full_text = Column(Text, nullable=False)
    summary = Column(Text, nullable=False)
    category = Column(String)
    gs_linkage = Column(String, nullable=False)
    tags = Column(Text)
    supporting_arguments = Column(Text, nullable=False)
    counter_arguments = Column(Text, nullable=False)
    way_forward = Column(Text, nullable=False)
    prelims_high_yield_facts = Column(Text, nullable=False)
    matched_via = Column(String, nullable=False)
    matched_micro_topic = Column(String)
    vector_match_score = Column(Float, default=0.0)
    is_academy_verified = Column(Boolean, default=False)
    is_supplemental = Column(Boolean, default=False)
    predicted_traps = Column(Text, nullable=True)
    image_url = Column(String, nullable=True)
    images = Column(JSON, default=list)
    priority = Column(String, default="medium")
    date_of_event = Column(String, nullable=True)
    newspaper_name = Column(String, nullable=True)
    date_fetched = Column(String, default=lambda: str(datetime.utcnow().date()))
    created_at = Column(DateTime, default=datetime.utcnow)


class TrendMetrics(CABase):
    __tablename__ = "trend_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    topic_tag = Column(String, unique=True, index=True, nullable=False)
    live_feed_frequency = Column(Integer, default=0)
    academy_pdf_frequency = Column(Integer, default=0)
    computed_density_score = Column(Float, default=0.0)
    last_calibrated = Column(DateTime, default=datetime.utcnow)
