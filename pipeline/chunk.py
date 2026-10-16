"""Optional: split extracted documents into passages so analyze.py can rank sections, not whole books.

Usage:
    python chunk.py <out_dir> <chunk_out_dir> [--words 1500] [--keep-all]
    python analyze.py <chunk_out_dir> ...

Consecutive pages are grouped until a passage reaches about --words words. Front/back matter,
index and blank pages, and pages flagged by validate.py, are skipped unless --keep-all is given.
Each passage is written as its own
record in <chunk_out_dir>/texts/,
named "<document> p<first>-<last>".
"""
import argparse
import csv
import json
from pathlib import Path

from textnorm import detect_language
from validate import page_type


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out_dir", type=Path)
    ap.add_argument("chunk_dir", type=Path)
    ap.add_argument("--words", type=int, default=1500)
    ap.add_argument("--keep-all", action="store_true")
    args = ap.parse_args()

    dest = args.chunk_dir / "texts"
    dest.mkdir(parents=True, exist_ok=True)
    total = 0
    # Pages that failed validate.py (tables of special characters, covers, garbled OCR) are skipped too.
    qfile = args.out_dir / "validation" / "page_quality.csv"
    flagged = set()
    if qfile.exists() and not args.keep_all:
        with open(qfile, encoding="utf-8") as f:
            flagged = {(r["file"], int(r["page"])) for r in csv.DictReader(f) if r["flag"]}
    for path in sorted((args.out_dir / "texts").glob("*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        buf, start, last = [], None, None

        def flush(end):
            nonlocal buf, start, total
            if buf:
                text = "\n\n".join(buf)
                name = f"{Path(rec['file']).stem} p{start}-{end}"
                (dest / f"{name}.json").write_text(json.dumps({
                    "file": name, "source": rec["file"], "first_page": start, "last_page": end,
                    "n_pages": end - start + 1, "needs_ocr": False, "language": detect_language(text),
                    "metadata": {"title": rec["metadata"].get("title", "")}, "pages": buf, "text": text,
                }, ensure_ascii=False), encoding="utf-8")
                total += 1
            buf, start = [], None

        for n, page in enumerate(rec["pages"], 1):
            if not args.keep_all and (page_type(page, n - 1, rec["n_pages"]) != "body"
                                      or (rec["file"], n) in flagged):
                flush(last)  # never let a passage run across skipped pages
                continue
            start, last = start or n, n
            buf.append(page)
            if sum(len(p.split()) for p in buf) >= args.words:
                flush(n)
        flush(last)
    print(f"Wrote {total} passages to {dest}")


if __name__ == "__main__":
    main()
