"""Step 1: extract text and metadata from a folder of PDFs.

Usage:
    python extract.py <pdf_dir> <out_dir>

Writes one JSON file per PDF into <out_dir>/texts/ plus <out_dir>/extraction_summary.csv.
Pages with almost no extractable text but with images are flagged as likely scanned
(those need OCR before analysis).
"""
import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

import pymupdf

from textnorm import detect_language, fix_visual_order, normalize

MIN_CHARS_PER_PAGE = 50  # below this a page is treated as "no text layer"


def clean_text(text: str) -> str:
    text = normalize(text)
    text = text.replace("­", "")                  # soft hyphens
    text = re.sub(r"-\n(\w)", r"\1", text)             # re-join hyphenated line breaks
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def strip_repeated_lines(pages: list[str]) -> list[str]:
    """Remove running headers/footers: short lines that repeat on >50% of pages."""
    if len(pages) < 4:
        return pages
    counts: dict[str, int] = {}
    for p in pages:
        for line in set(l.strip() for l in p.splitlines()):
            key = re.sub(r"\d+", "#", line)
            if 0 < len(key) < 80:
                counts[key] = counts.get(key, 0) + 1
    repeated = {k for k, c in counts.items() if c > len(pages) * 0.5}
    return [
        "\n".join(l for l in p.splitlines() if re.sub(r"\d+", "#", l.strip()) not in repeated)
        for p in pages
    ]


def extract_pdf(path: Path) -> dict:
    doc = pymupdf.open(path)
    pages, scanned_pages = [], 0
    for page in doc:
        text = page.get_text("text", sort=True)
        if len(text.strip()) < MIN_CHARS_PER_PAGE and page.get_images():
            scanned_pages += 1
        pages.append(text)
    pages = [clean_text(p) for p in strip_repeated_lines(pages)]
    fixed = False
    if detect_language("\n".join(pages)) in ("fa", "mixed"):
        joined, fixed = fix_visual_order("\n\f".join(pages))
        pages = joined.split("\n\f") if fixed else pages
    full = "\n\n".join(pages)
    meta = {k: v for k, v in (doc.metadata or {}).items() if v}
    n_pages = len(doc)
    doc.close()
    return {
        "file": path.name,
        "sha1": hashlib.sha1(path.read_bytes()).hexdigest(),
        "n_pages": n_pages,
        "scanned_pages": scanned_pages,
        "needs_ocr": n_pages > 0 and scanned_pages / n_pages > 0.3,
        "language": detect_language(full),
        "visual_order_fixed": fixed,
        "metadata": meta,
        "pages": pages,
        "text": full,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf_dir", type=Path)
    ap.add_argument("out_dir", type=Path)
    ap.add_argument("--txt", action="store_true", help="also write a plain .txt copy of each document for reading")
    args = ap.parse_args()

    texts_dir = args.out_dir / "texts"
    texts_dir.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(p for p in args.pdf_dir.rglob("*") if p.suffix.lower() == ".pdf")
    if not pdfs:
        sys.exit(f"No PDFs found in {args.pdf_dir}")

    rows, seen_hashes = [], {}
    for path in pdfs:
        try:
            rec = extract_pdf(path)
        except Exception as e:  # corrupt / encrypted files shouldn't stop the batch
            print(f"FAILED  {path.name}: {e}")
            rows.append({"file": path.name, "status": f"error: {e}"})
            continue
        status = "ok"
        if rec["sha1"] in seen_hashes:
            status = f"exact duplicate of {seen_hashes[rec['sha1']]} (skipped)"
        else:
            seen_hashes[rec["sha1"]] = path.name
            if rec["needs_ocr"]:
                status = "needs OCR (scanned)"
        if "skipped" not in status:
            (texts_dir / f"{path.stem}.json").write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
            if args.txt:
                body = "\n\n".join(f"===== Page {i} =====\n{p}" for i, p in enumerate(rec["pages"], 1))
                (texts_dir / f"{path.stem}.txt").write_text(body, encoding="utf-8")
        rows.append({
            "file": path.name, "status": status, "pages": rec["n_pages"],
            "scanned_pages": rec["scanned_pages"], "chars": len(rec["text"]),
            "language": rec["language"], "visual_order_fixed": rec["visual_order_fixed"],
            "title": rec["metadata"].get("title", ""),
        })
        print(f"{status:<22} {rec['language']:<7} {path.name}  ({rec['n_pages']} pages, {len(rec['text']):,} chars)"
              + ("  [fixed reversed Persian]" if rec["visual_order_fixed"] else ""))

    with open(args.out_dir / "extraction_summary.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["file", "status", "pages", "scanned_pages", "chars", "language",
                                          "visual_order_fixed", "title"])
        w.writeheader()
        w.writerows(rows)
    print(f"\nExtracted {len(rows)} PDFs -> {texts_dir}")


if __name__ == "__main__":
    main()
