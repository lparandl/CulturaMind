"""Step 1b: validate extraction quality before trusting any analysis.

Usage:
    python validate.py <pdf_dir> <out_dir> [--sample 12] [--wordlist /usr/share/dict/words]
                       [--reference other_extraction_dir]

Writes into <out_dir>/validation/:
    page_quality.csv   one row per page: words, valid-word rate, noise rate, page type, flag
    summary.csv        one row per document
    review.html        random sample of pages: page image next to extracted text, for a
                       person to check by hand (the only real ground truth)

"Valid word" = in the English word list, or occurring >= 3 times in the whole collection
(so repeated proper names like Ahura Mazda or Tistrya are not counted as OCR errors;
OCR errors are mostly one-off strings). Persian pages are scored on noise only unless a
Persian word list is passed with --wordlist.
"""
import argparse
import base64
import html
import json
import random
import re
from collections import Counter
from pathlib import Path

import pandas as pd
import pymupdf

from textnorm import detect_language, tokens

NOISE_RE = re.compile(r"[^\w\s.,;:!?'\"()\[\]\-–—‘’“”/&%§*…‌]", re.UNICODE)


CATALOGUE_RE = re.compile(r"\b(?:fcap|8vo|4to|svo|cloth|stitched|Clarendon Press|Second Edition)\b|\b\d+s\. ?\d*d\.",
                          re.IGNORECASE)
INDEX_LINE_RE = re.compile(r",\s*\d+[,.;]?$")  # index entries end in page numbers: "Mithra, 119, 136."


def page_type(text: str, n: int, n_pages: int) -> str:
    words = text.split()
    if len(words) < 20:
        return "blank/figure"
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    digits = sum(c.isdigit() for c in text) / max(len(text), 1)
    index_lines = sum(len(l) < 90 and bool(INDEX_LINE_RE.search(l)) for l in lines) / max(len(lines), 1)
    if n > n_pages * 0.6 and (index_lines > 0.3 or digits > 0.12):
        return "index"
    if len(CATALOGUE_RE.findall(text)) >= 4:
        return "publisher catalogue"
    if n < n_pages * 0.04 or n > n_pages * 0.97:
        return "front/back matter"
    return "body"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf_dir", type=Path)
    ap.add_argument("out_dir", type=Path)
    ap.add_argument("--sample", type=int, default=12, help="pages per document in review.html")
    ap.add_argument("--wordlist", type=Path, default=Path("/usr/share/dict/words"))
    ap.add_argument("--reference", type=Path, help="folder of .txt files from another extractor to compare against")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    vdir = args.out_dir / "validation"
    vdir.mkdir(parents=True, exist_ok=True)
    words = {w.strip().lower() for w in args.wordlist.read_text(encoding="utf-8", errors="ignore").split()} \
        if args.wordlist.exists() else set()
    recs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((args.out_dir / "texts").glob("*.json"))]
    corpus_freq = Counter(t for r in recs for t in tokens(r["text"]))

    rows = []
    for r in recs:
        for n, text in enumerate(r["pages"]):
            toks = tokens(text)
            alpha = [t for t in toks if len(t) >= 3]
            valid = [t for t in alpha if t in words or corpus_freq[t] >= 3]
            lang = detect_language(text)
            rows.append({
                "file": r["file"], "page": n + 1, "language": lang,
                "type": page_type(text, n, r["n_pages"]),
                "words": len(toks),
                "valid_word_rate": round(len(valid) / len(alpha), 3) if alpha and (lang != "fa" or words) else None,
                "noise_rate": round(len(NOISE_RE.findall(text)) / max(len(text), 1), 4),
                "hapax_rate": round(sum(corpus_freq[t] == 1 for t in alpha) / max(len(alpha), 1), 3),
            })
    pq = pd.DataFrame(rows)
    pq["flag"] = ""
    body = pq.type == "body"
    pq.loc[body & (pq.valid_word_rate < 0.85), "flag"] = "low valid-word rate"
    pq.loc[body & (pq.noise_rate > 0.02), "flag"] = "noisy"
    pq.to_csv(vdir / "page_quality.csv", index=False)

    summ = pq.groupby("file").agg(
        pages=("page", "size"),
        body_pages=("type", lambda s: int((s == "body").sum())),
        blank_pages=("type", lambda s: int((s == "blank/figure").sum())),
        words=("words", "sum"),
        valid_word_rate_body=("valid_word_rate", lambda s: round(s[pq.loc[s.index, "type"] == "body"].mean(), 3)),
        noise_rate_body=("noise_rate", lambda s: round(s[pq.loc[s.index, "type"] == "body"].mean(), 4)),
        flagged_pages=("flag", lambda s: int((s != "").sum())),
    ).reset_index()

    if args.reference:
        # Pair each document with the reference .txt whose filename shares most words, then compare
        # word multisets: 1.0 = same words, low = one extractor lost or garbled text.
        refs = list(args.reference.glob("*.txt"))
        name_words = lambda s: set(re.findall(r"[a-z0-9]+", s.lower()))
        sims, ref_words = {}, {}
        for r in recs:
            ref = max(refs, key=lambda p: len(name_words(p.stem) & name_words(Path(r["file"]).stem)), default=None)
            if ref is None:
                continue
            a, b = Counter(tokens(r["text"])), Counter(tokens(ref.read_text(encoding="utf-8", errors="ignore")))
            overlap = sum((a & b).values())
            sims[r["file"]] = round(2 * overlap / max(sum(a.values()) + sum(b.values()), 1), 3)
            ref_words[r["file"]] = f"{ref.name} ({sum(b.values()):,} words)"
        summ["reference"] = summ.file.map(ref_words)
        summ["reference_similarity"] = summ.file.map(sims)
    summ.to_csv(vdir / "summary.csv", index=False)

    write_review(args, recs, pq, vdir)
    print(summ.to_string(index=False))
    print(f"\nWrote {vdir}/page_quality.csv, summary.csv, review.html")


def write_review(args, recs, pq, vdir: Path) -> None:
    rnd = random.Random(args.seed)
    parts = ["<!doctype html><meta charset=utf-8><title>Extraction review</title><style>"
             "body{font-family:system-ui;margin:16px;background:#fff;color:#111}"
             ".pg{display:grid;grid-template-columns:1fr 1fr;gap:12px;border-top:2px solid #ccc;padding:12px 0}"
             "img{width:100%;border:1px solid #ddd}pre{white-space:pre-wrap;font-size:12px;margin:0}"
             "h2{font-size:15px;margin:4px 0}.m{color:#555;font-size:12px}</style>"
             "<h1>Extraction review sample</h1><p>For each page, compare the text with the image and record "
             "errors in <code>manual_check.csv</code> (file, page, words_checked, errors). "
             "Character/word error rate = errors / words_checked.</p>"]
    for r in recs:
        pages = pq[(pq.file == r["file"]) & (pq.type == "body")].page.tolist()
        if not pages:
            continue
        pick = sorted(rnd.sample(pages, min(args.sample, len(pages))))
        doc = pymupdf.open(args.pdf_dir / r["file"])
        for p in pick:
            img = doc[p - 1].get_pixmap(dpi=90).tobytes("jpeg", jpg_quality=70)
            row = pq[(pq.file == r["file"]) & (pq.page == p)].iloc[0]
            parts.append(
                f"<div class=pg><div><h2>{html.escape(r['file'])} — page {p}</h2>"
                f"<p class=m>valid-word rate {row.valid_word_rate} · noise {row.noise_rate} · {row.flag or 'ok'}</p>"
                f"<img src='data:image/jpeg;base64,{base64.b64encode(img).decode()}'></div>"
                f"<pre>{html.escape(r['pages'][p - 1])}</pre></div>")
        doc.close()
    (vdir / "review.html").write_text("\n".join(parts), encoding="utf-8")


if __name__ == "__main__":
    main()
