import unicodedata
from fpdf import FPDF


def sanitize_for_pdf(text: str) -> str:
    return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')


class QuestionPaperPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(180, 180, 180)
        self.cell(0, 6, "UPSC AGENT V2 - PRACTICE TEST", align="C")
        self.ln(4)
        self.set_draw_color(200, 200, 200)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)
        self.set_text_color(0, 0, 0)

    def footer(self):
        self.set_y(-15)
        self.set_text_color(150, 150, 150)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")
        self.set_text_color(0, 0, 0)


def generate_question_pdf(questions: list, topic: str, output_path: str, session_id: str = ""):
    pdf = QuestionPaperPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 12, f"UPSC Prelims - {topic}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 8, f"Total Questions: {len(questions)}", align="C", new_x="LMARGIN", new_y="NEXT")
    if session_id:
        pdf.cell(0, 8, f"Session: {session_id}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    for i, q in enumerate(questions, 1):
        text = q.get("question_text", "")
        options = q.get("options", {})

        lines_needed = 2 + len(text) // 85 + len(options) * 2 + 2
        if pdf.get_y() + lines_needed * 6 > 270:
            pdf.add_page()

        pdf.set_font("Helvetica", "B", 11)
        pdf.set_x(10)
        pdf.multi_cell(0, 6, sanitize_for_pdf(f"{i}. {text}"), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        pdf.set_font("Helvetica", "", 10)
        for key in ("A", "B", "C", "D"):
            opt_text = options.get(key, "")
            pdf.set_x(10)
            pdf.multi_cell(0, 6, sanitize_for_pdf(f"   {key}. {opt_text}"), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

    pdf.output(output_path)


def generate_answer_key_pdf(entries: list[dict], output_path: str, session_id: str = ""):
    """Generate answer key PDF with explanations for diagnostic."""
    pdf = QuestionPaperPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 12, "UPSC Diagnostic - Answer Key", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 8, f"Total Questions: {len(entries)}", align="C", new_x="LMARGIN", new_y="NEXT")
    if session_id:
        pdf.cell(0, 8, f"Session: {session_id}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    for i, e in enumerate(entries, 1):
        text = e.get("question_text", "")
        options = e.get("options", {})
        correct = e.get("correct_key", "")
        trap_type = e.get("trap_type", "")
        trap_mech = e.get("trap_mechanism", "")
        explanation = e.get("correct_explanation", "")

        lines_needed = 2 + len(text) // 85 + len(options) * 2 + 8
        if pdf.get_y() + lines_needed * 6 > 270:
            pdf.add_page()

        pdf.set_font("Helvetica", "B", 11)
        pdf.set_x(10)
        pdf.multi_cell(0, 6, sanitize_for_pdf(f"{i}. {text}"), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)

        pdf.set_font("Helvetica", "", 10)
        for key in ("A", "B", "C", "D"):
            opt_text = options.get(key, "")
            prefix = ">> " if key == correct else "   "
            pdf.set_x(10)
            pdf.multi_cell(0, 6, sanitize_for_pdf(f"{prefix}{key}. {opt_text}"), new_x="LMARGIN", new_y="NEXT")

        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(0, 100, 0)
        pdf.set_x(10)
        pdf.multi_cell(0, 5, sanitize_for_pdf(f"Correct Answer: {correct}"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)

        if trap_type:
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_x(10)
            pdf.multi_cell(0, 5, sanitize_for_pdf(f"Trap: {trap_type}"), new_x="LMARGIN", new_y="NEXT")
        if trap_mech:
            pdf.set_font("Helvetica", "", 9)
            pdf.set_x(10)
            pdf.multi_cell(0, 5, sanitize_for_pdf(f"How it traps: {trap_mech}"), new_x="LMARGIN", new_y="NEXT")
        if explanation:
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(0, 0, 150)
            pdf.set_x(10)
            pdf.multi_cell(0, 5, sanitize_for_pdf(f"Why correct: {explanation}"), new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(0, 0, 0)

        pdf.ln(4)

    pdf.output(output_path)
