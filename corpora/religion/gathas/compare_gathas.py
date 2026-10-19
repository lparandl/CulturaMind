"""Compare two English translations of the Gathas chapter by chapter and verse by verse.

Usage:
    python compare_gathas.py <mills_json> <azargoshasb_pdf> <out_dir>

<mills_json> is extract.py output for Zend-Avesta Part III (L. H. Mills, SBE 31, 1887), which holds
the Gathas (Yasna 28-34, 43-51, 53) with Mills' introductions, translations and footnotes.
<azargoshasb_pdf> is Mobed Firouz Azargoshasb's "Translation of Gathas". It is read straight from
the PDF because extract.py drops its "Verse N:" labels as repeated page headers.

Only Mills' translation sections are kept: each chapter's introduction (before "Translation.")
and the footnotes at the foot of each page are dropped, so what is compared is translation against
translation. Writes chapters.csv, verses.csv, similarity_matrix.csv and report.md to <out_dir>.
"""
import argparse
import csv
import json
import re
from pathlib import Path

import numpy as np
import fitz
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Chapter order as Mills prints them (he moves Y. 29 before Y. 28).
MILLS_ORDER = [29, 28, 30, 31, 32, 33, 34, 43, 44, 45, 46, 47, 48, 49, 50, 51, 53]
CHAPTERS = sorted(MILLS_ORDER)
ROMAN = {28: "XXVIII", 29: "XXIX", 30: "XXX", 31: "XXXI", 32: "XXXII", 33: "XXXIII", 34: "XXXIV",
         43: "XLIII", 44: "XLIV", 45: "XLV", 46: "XLVI", 47: "XLVII", 48: "XLVIII", 49: "XLIX",
         50: "L", 51: "LI", 53: "LIII"}
# OCR misreads of verse numbers at the start of a line: "i." = 1, "I I." / "ii." = 11, "l8." = 18.
OCR_DIGITS = str.maketrans({"i": "1", "I": "1", "l": "1", "o": "0", "O": "0"})
VERSE_START = re.compile(r"^\s*([0-9iIlo]{1,2}|[iIl1] [iIl1])\s?\.\s", re.M)
STOP_PHRASES = re.compile(r"\b(o|thou|thee|thy|thine|ye|unto|verily|yea)\b")


def clean_page(page: str) -> str:
    """Drop the running header and the footnote block at the foot of a Mills page."""
    lines = page.split("\n")
    if lines and re.match(r"^\s*[\dIlO ]{0,6}(THE GATH|YASNA [IVXL]+\.)", lines[0]):
        lines = lines[1:]
    text = "\n".join(lines)
    # Footnotes begin with a numeral after a blank line, past the top of the page.
    m = re.search(r"\n\s*\n\s*[1-9]\d?\s+[A-Z'‘\"(]", text[len(text) // 4:])
    if m:
        text = text[: len(text) // 4 + m.start()]
    text = re.sub(r"(?<=[A-Za-z)])[1-9x*]\b", "", text)  # footnote markers such as "Kine1"
    return text


def mills_chapters(rec: dict) -> dict:
    pages = rec["pages"]
    first = next(i for i, p in enumerate(pages) if re.search(r"^YASNA XXIX\.\s*$", p, re.M))
    last = next(i for i, p in enumerate(pages) if i > first and p.lstrip().startswith("THE YASNA."))
    body = "\n".join(clean_page(p) for p in pages[first:last])
    marks = [m.end() for m in re.finditer(r"^\s*Translation\.\s*$", body, re.M)]
    if len(marks) != len(MILLS_ORDER):
        raise SystemExit(f"expected {len(MILLS_ORDER)} 'Translation.' markers in Mills, found {len(marks)}")
    out = {}
    # A chapter's translation runs from its "Translation." marker to the heading that opens the
    # next chapter's introduction (a Yasna heading, or a Gatha heading for the first chapter of a Gatha).
    heading = re.compile(r"^(THE GATHA\(A\)|YASNA [IVXL]+[.,]).*$", re.M)
    for k, ch in enumerate(MILLS_ORDER):
        stop = marks[k + 1] if k + 1 < len(marks) else len(body)
        nxt = heading.search(body, marks[k], stop) if k + 1 < len(marks) else None
        out[ch] = body[marks[k]:nxt.start() if nxt else stop]
    return out


def split_mills_verses(text: str) -> dict:
    verses, marks = {}, list(VERSE_START.finditer(text))
    expected = 1
    kept = []
    for m in marks:  # keep only numbers that continue the sequence, so stray OCR hits are ignored
        n = int(m.group(1).replace(" ", "").translate(OCR_DIGITS)) if re.fullmatch(
            r"[0-9iIlo ]+", m.group(1)) else None
        if n == expected or (n and expected < n <= expected + 2):
            kept.append((n, m))
            expected = n + 1
    for j, (n, m) in enumerate(kept):
        end = kept[j + 1][1].start() if j + 1 < len(kept) else len(text)
        verses[n] = " ".join(text[m.end():end].split())
    return verses


def azargoshasb_chapters(pdf: Path) -> dict:
    with fitz.open(pdf) as doc:
        text = "\n".join(page.get_text() for page in doc)
    text = re.sub(r"^\(\d+\) .*$", "", text, flags=re.M)  # footnotes such as "(1) Please refer to ..."
    heads = list(re.finditer(r"^Yasna (\d{2})\s*$", text, re.M))
    heads = [h for h in heads if int(h.group(1)) in CHAPTERS and h.start() > text.find("Preface")]
    seen, out = set(), {}
    for j, h in enumerate(heads):
        ch = int(h.group(1))
        if ch in seen:
            continue
        seen.add(ch)
        end = heads[j + 1].start() if j + 1 < len(heads) else len(text)
        out[ch] = text[h.end():end]
    return out


def split_azargoshasb_verses(text: str) -> dict:
    parts = re.split(r"^Verse (\d{1,2}):\s*$", text, flags=re.M)
    return {int(parts[i]): " ".join(re.sub(r"^\s*\d+\s*$", "", parts[i + 1], flags=re.M).split())
            for i in range(1, len(parts) - 1, 2)}


def normalise(t: str) -> str:
    return STOP_PHRASES.sub(" ", re.sub(r"[^a-z ]", " ", t.lower()))


def shared_ngrams(a: str, b: str, n: int = 5) -> int:
    def grams(t):
        w = t.split()
        return {tuple(w[i:i + n]) for i in range(len(w) - n + 1)}
    return len(grams(normalise(a)) & grams(normalise(b)))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mills_json", type=Path)
    ap.add_argument("azargoshasb_pdf", type=Path)
    ap.add_argument("out_dir", type=Path)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    mills = mills_chapters(json.loads(args.mills_json.read_text(encoding="utf-8")))
    azar = azargoshasb_chapters(args.azargoshasb_pdf)
    m_verses = {c: split_mills_verses(mills[c]) for c in CHAPTERS}
    # Mills numbers the Ahunavaiti's opening formula ("A strengthening blessing is the thought...")
    # as Y. 28.1; Azargoshasb gives it unnumbered, so shift Mills' Y. 28 to the usual numbering.
    if m_verses[28].get(1, "").startswith("(A strengthening blessing"):
        m_verses[28] = {n - 1: v for n, v in m_verses[28].items() if n > 1}
    a_verses = {c: split_azargoshasb_verses(azar.get(c, "")) for c in CHAPTERS}

    # Fit one vocabulary on both translations so the scores are comparable.
    m_docs = [normalise(" ".join(m_verses[c].values())) for c in CHAPTERS]
    a_docs = [normalise(" ".join(a_verses[c].values())) for c in CHAPTERS]
    vec = TfidfVectorizer(stop_words="english", sublinear_tf=True, min_df=1).fit(m_docs + a_docs)
    sim = cosine_similarity(vec.transform(m_docs), vec.transform(a_docs))

    with open(args.out_dir / "similarity_matrix.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["mills \\ azargoshasb"] + [f"Y{c}" for c in CHAPTERS])
        for i, c in enumerate(CHAPTERS):
            w.writerow([f"Y{c}"] + [f"{x:.3f}" for x in sim[i]])

    chapter_rows, verse_rows = [], []
    for i, c in enumerate(CHAPTERS):
        mv, av = m_verses[c], a_verses[c]
        off = np.delete(sim[i], i)
        chapter_rows.append({
            "chapter": f"Yasna {c}", "mills_verses": len(mv), "azargoshasb_verses": len(av),
            "mills_words": sum(len(v.split()) for v in mv.values()),
            "azargoshasb_words": sum(len(v.split()) for v in av.values()),
            "same_chapter_similarity": round(float(sim[i, i]), 3),
            "best_other_chapter_similarity": round(float(off.max()), 3),
            "best_match": f"Yasna {CHAPTERS[int(np.argmax(sim[i]))]}",
            "shared_5grams": shared_ngrams(" ".join(mv.values()), " ".join(av.values())),
        })
        common = sorted(set(mv) & set(av))
        if common:
            ms = vec.transform([normalise(mv[n]) for n in common])
            az = vec.transform([normalise(av[n]) for n in common])
            vs = cosine_similarity(ms, az)
            for j, n in enumerate(common):
                verse_rows.append({"chapter": c, "verse": n, "similarity": round(float(vs[j, j]), 3),
                                   "mills_words": len(mv[n].split()), "azargoshasb_words": len(av[n].split()),
                                   "mills": mv[n], "azargoshasb": av[n]})

    for name, rows in (("chapters.csv", chapter_rows), ("verses.csv", verse_rows)):
        with open(args.out_dir / name, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)

    diag_best = sum(r["best_match"] == r["chapter"] for r in chapter_rows)
    mw = sum(r["mills_words"] for r in chapter_rows)
    aw = sum(r["azargoshasb_words"] for r in chapter_rows)
    lines = [
        "# Gathas: Mills (Zend-Avesta Part III) vs Azargoshasb", "",
        f"- Chapters found: Mills {sum(1 for c in CHAPTERS if m_verses[c])}/17, "
        f"Azargoshasb {sum(1 for c in CHAPTERS if a_verses[c])}/17.",
        f"- Verses: Mills {sum(len(v) for v in m_verses.values())}, "
        f"Azargoshasb {sum(len(v) for v in a_verses.values())}.",
        f"- Words of translation: Mills {mw:,}, Azargoshasb {aw:,}.",
        f"- Chapters whose closest match in the other translation is the same chapter: {diag_best}/17.",
        f"- Shared 5-word sequences across all chapters: {sum(r['shared_5grams'] for r in chapter_rows)}.",
        "", "| Chapter | Verses (M / A) | Words (M / A) | Same-chapter sim. | Best other | Shared 5-grams |",
        "|---|---|---|---|---|---|",
    ]
    for r in chapter_rows:
        lines.append(f"| {r['chapter']} | {r['mills_verses']} / {r['azargoshasb_verses']} | "
                     f"{r['mills_words']} / {r['azargoshasb_words']} | {r['same_chapter_similarity']} | "
                     f"{r['best_other_chapter_similarity']} | {r['shared_5grams']} |")
    (args.out_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
