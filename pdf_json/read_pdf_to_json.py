"""
Read test.pdf, upload to Gemini via Files API, structure content into
question objects via Gemini API (gemini-3.1-pro-preview), write JSON.
Requires GEMINI_API_KEY in .env.
"""

import json
import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

# --- config ---
PDF_PATH = Path(__file__).resolve().parent / "test.pdf"
OUTPUT_JSON_PATH = Path(__file__).resolve().parent / "test_questions.json"
MODEL_ID = "gemini-3.1-pro-preview"

SCHEMA_PROMPT = """You are given a PDF document (exam or study material). Read all pages carefully.

Extract every question/answer block into a structured list. For each block output exactly one JSON object with these keys (no extra keys):
- "id": string, e.g. "q-eng-001", "q-eng-002" (use question number to form id).
- "questionNo": string, e.g. "Q1", "Q2".
- "title": string, the question title or prompt (one line/sentence).
- "desc": string, the full description or answer text (can be multi-line).
- "pageNum": integer, 1-based page number where this question appears.
- "marks": integer, marks for the question (use 0 if not found).
- "diagramDescriptions": array of strings, any descriptions of diagrams/flowcharts/maps mentioned (empty array if none).

Output ONLY a single JSON array of such objects. No markdown, no explanation. If the document has no clear questions, return one object with the whole content in "desc" and pageNum 1, id "q-eng-001", questionNo "Q1", title "Content", marks 0, diagramDescriptions [].
Valid JSON array example: [{"id":"q-eng-001","questionNo":"Q1","title":"...","desc":"...","pageNum":1,"marks":8,"diagramDescriptions":["..."]}]
"""


def load_env() -> str:
    load_dotenv()
    key = os.getenv("GEMINI_API_KEY")
    if not key or not key.strip():
        print("Error: GEMINI_API_KEY is not set. Add it to a .env file in the project root.", file=sys.stderr)
        sys.exit(1)
    return key.strip()


def wait_for_file_active(client: genai.Client, file: types.File, max_wait_sec: int = 120) -> types.File:
    """Poll until file state is ACTIVE (or FAILED)."""
    name = file.name
    if not name:
        return file
    start = time.monotonic()
    while time.monotonic() - start < max_wait_sec:
        f = client.files.get(name=name)
        state = str(getattr(f, "state", "") or "").upper()
        if state == "ACTIVE":
            return f
        if state == "FAILED":
            raise RuntimeError(f"File processing failed: {name}")
        time.sleep(2)
    raise TimeoutError(f"File {name} did not become ACTIVE within {max_wait_sec}s")


def extract_json_from_response(response_text: str) -> list:
    """Strip markdown code fence if present and parse JSON array."""
    text = response_text.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if m:
        text = m.group(1).strip()
    data = json.loads(text)
    if not isinstance(data, list):
        data = [data]
    return data


def normalize_question(obj: dict) -> dict:
    """Ensure types: pageNum and marks int, diagramDescriptions list of strings."""
    return {
        "id": str(obj.get("id", "q-eng-001")),
        "questionNo": str(obj.get("questionNo", "Q1")),
        "title": str(obj.get("title", "")),
        "desc": str(obj.get("desc", "")),
        "pageNum": int(obj.get("pageNum", 1)),
        "marks": int(obj.get("marks", 0)),
        "diagramDescriptions": (
            [str(x) for x in obj.get("diagramDescriptions", [])]
            if isinstance(obj.get("diagramDescriptions"), list)
            else []
        ),
    }


def main() -> None:
    api_key = load_env()
    client = genai.Client(api_key=api_key)

    if not PDF_PATH.exists():
        print(f"Error: PDF not found at {PDF_PATH}", file=sys.stderr)
        sys.exit(1)

    print("Uploading PDF...", flush=True)
    pdf_file = client.files.upload(file=str(PDF_PATH))
    state = str(getattr(pdf_file, "state", "") or "").upper()
    if not pdf_file.uri and state == "PROCESSING":
        print("Waiting for file processing...")
        pdf_file = wait_for_file_active(client, pdf_file)

    if not pdf_file.uri:
        print("Error: File has no URI. Cannot use in generate_content.", file=sys.stderr)
        sys.exit(1)

    print(f"Calling {MODEL_ID}...", flush=True)
    response = client.models.generate_content(
        model=MODEL_ID,
        contents=[pdf_file, SCHEMA_PROMPT],
    )

    response_text = response.text if hasattr(response, "text") and response.text else None
    if not response_text:
        print("Error: Gemini returned no text.", file=sys.stderr)
        sys.exit(1)

    try:
        raw_list = extract_json_from_response(response_text)
    except json.JSONDecodeError as e:
        print(f"Error: Could not parse Gemini response as JSON: {e}", file=sys.stderr)
        print("Response snippet:", response_text[:500], file=sys.stderr)
        sys.exit(1)

    questions = [normalize_question(o) for o in raw_list]

    OUTPUT_JSON_PATH.write_text(json.dumps(questions, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(questions)} question(s) to {OUTPUT_JSON_PATH}", flush=True)


if __name__ == "__main__":
    main()
