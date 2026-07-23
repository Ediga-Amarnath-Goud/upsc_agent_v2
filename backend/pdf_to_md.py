from pathlib import Path
from llama_parse import LlamaParse

DATA_DIR = Path(__file__).resolve().parent / "data"
MARKDOWN_DIR = DATA_DIR / "markdown"
MARKDOWN_DIR.mkdir(exist_ok=True)


def convert_pdf_to_markdown(pdf_path: str) -> str:
    parser = LlamaParse(result_type="markdown", num_workers=1)
    docs = parser.load_data(pdf_path)
    md_text = "\n\n".join(d.text for d in docs)

    src = Path(pdf_path)
    md_path = MARKDOWN_DIR / f"{src.stem}.md"
    md_path.write_text(md_text, encoding="utf-8")
    return md_text
