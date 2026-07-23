import requests
import PyPDF2
import io
import re
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data" / "answer_keys"
DATA_DIR.mkdir(parents=True, exist_ok=True)

urls = {
    2014: "https://cdn-images.prepp.in/public/image/upsc-prelims-2014-august-24-gs-i-paper-i-answer-key-pdf-1778479552.pdf",
    2015: "https://cdn-images.prepp.in/public/image/upsc-prelims-2015-august-23-gs-i-paper-ianswer-key-pdf-1778477493.pdf",
    2016: "https://cdn-images.prepp.in/public/image/upsc-prelims-2016-august-07-gs-i-paper-i-question-paper-and-answer-key-1778477493.pdf",
}

for year, url in urls.items():
    print(f"\n{year}: downloading...")
    try:
        resp = requests.get(url, timeout=30)
        if resp.status_code != 200:
            print(f"  HTTP {resp.status_code}")
            continue
        pdf_file = io.BytesIO(resp.content)
        reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in reader.pages:
            text += page.extract_text()

        print(f"  {len(reader.pages)} pages, {len(text)} chars")

        # Try multiple patterns
        patterns = [
            r"(\d{1,3})\s+([A-D])\s",
            r"(\d{1,3})\.?\s*([A-D])\b",
            r"(\d{1,3})\s*[.)]\s*([A-D])\b",
        ]

        best = []
        for p in patterns:
            matches = re.findall(p, text)
            if len(matches) > len(best):
                best = matches

        if best:
            # Filter to valid range 1-100, deduplicate
            seen = set()
            answers = {}
            for num_str, ans in best:
                num = int(num_str)
                if 1 <= num <= 100 and ans in "ABCD":
                    if num not in seen:
                        answers[num] = ans
                        seen.add(num)
            print(f"  Extracted {len(answers)} answers")
            if answers:
                print(f"  First 10: {dict(sorted(answers.items())[:10])}")
                print(f"  Last 10: {dict(sorted(answers.items())[-10:])}")
                # Save
                cache_path = DATA_DIR / f"{year}.json"
                cache_path.write_text(json.dumps(answers, indent=2))
                print(f"  Saved to {cache_path}")
        else:
            print(f"  No answer patterns found!")
            print(f"  Raw text preview: {text[:500]}")
    except Exception as e:
        print(f"  Error: {e}")
