from pydantic import BaseModel, ConfigDict


class TestRequest(BaseModel):
    topic_studied: str
    question_count: int = 10
    quality_check: bool = True


class SubmitAnswerPayload(BaseModel):
    session_id: str
    question_index: int
    response: str
    time_taken: int | None = None


class GenerateTestResponse(BaseModel):
    session_id: str
    total_questions: int
    pdf_url: str
    time_limit_seconds: int = 1800


class SubmitAnswerResponse(BaseModel):
    correct: bool
    correct_answer: str
    trap_explanation: str
    most_likely_wrong_reason: str
    score: int
    elo_delta: int


class ActivityLogResponse(BaseModel):
    log_id: int
    source_pdf: str
    stage: str
    progress: str | None = None
    status: str
    started_at: str


class ProfileCreatePayload(BaseModel):
    name: str
    age: int
    gender: str


class ProfileStatusResponse(BaseModel):
    registered: bool
    diagnostic_completed: bool
    name: str | None


class StudentProfileResponse(BaseModel):
    name: str
    age: int | None
    gender: str | None
    diagnostic_completed: bool
    onboarding_complete: bool
    current_elo: int
    subject_elos: dict
    total_attempted: int
    total_correct: int
    accuracy: float


class TrapAnalysisOutput(BaseModel):
    trap_type: str
    trap_mechanism: str
    distraction_analysis: dict
    most_likely_wrong: str
    most_likely_wrong_reason: str
    related_concepts: list[str]
    difficulty_tier: int


class GeneratedQuestion(BaseModel):
    question_text: str
    options: dict
    difficulty_tier: int


class AnswerKeyEntry(BaseModel):
    correct_answer: str
    correct_explanation: str
    trap_type: str = ""
    trap_explanation: str = ""
    most_likely_wrong_answer: str
    most_likely_wrong_reason: str
    difficulty_tier: int


class OMRQuestionResult(BaseModel):
    question_index: int
    response: str
    correct: bool
    correct_answer: str
    trap_explanation: str
    most_likely_wrong_reason: str


class OMRSubmitResponse(BaseModel):
    session_id: str
    total_questions: int
    answered_count: int
    correct_count: int
    score: int
    elo_delta: int
    results: list[OMRQuestionResult]


class DiagnosticSubmitPayload(BaseModel):
    session_id: str
    responses: dict[int, str]
    time_taken: int | None = None
    name: str | None = None
    age: int | None = None
    gender: str | None = None


class GenerationOutput(BaseModel):
    questions: list[GeneratedQuestion]
    answer_key: list[AnswerKeyEntry]


class TrapForecastSchema(BaseModel):
    trap_type: str
    mechanism: str
    elimination_clue: str


class CuratedCAResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    issue_id: str
    title: str
    source_url: str
    source: str | None
    summary: str
    category: str | None
    gs_linkage: str
    tags: list[str] = []
    supporting_arguments: list[str] = []
    counter_arguments: list[str] = []
    way_forward: list[str] = []
    prelims_high_yield_facts: list[str] = []
    matched_via: str
    matched_micro_topic: str | None
    is_academy_verified: bool
    is_supplemental: bool
    predicted_traps: TrapForecastSchema | None
    image_url: str | None
    images: list[str] = []
    priority: str
    newspaper_name: str | None
    date_of_event: str | None
    date_fetched: str


class CuratedCAListResponse(BaseModel):
    total: int
    page: int
    per_page: int
    items: list[CuratedCAResponse]
