"""Step 2: NLP analysis + ranking of extracted documents for the initial "core" set.

Usage:
    python analyze.py <out_dir> [--brief brief.txt] [--select 20] [--topics 0]

Reads <out_dir>/texts/*.json (produced by extract.py) and writes:
    <out_dir>/document_scores.csv   every document with all metrics and its final score
    <out_dir>/topics.csv            discovered topics and their top terms
    <out_dir>/report.md             human-readable summary and the recommended core set

Per-document signals (each scaled to 0..1):
    quality     - is the extracted text clean? (text layer present, letters vs. garbage)
    substance   - enough content to be useful (log-scaled word count)
    richness    - vocabulary diversity (moving-average type/token ratio)
    centrality  - how representative the document is of the whole collection
    relevance   - similarity to your project brief (only if --brief is given)
The core set is then chosen greedily with Maximal Marginal Relevance, so it covers
different topics instead of picking ten near-identical documents, and near-duplicates
are never selected together.
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import NMF, TruncatedSVD
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import normalize

from textnorm import PERSIAN_STOPWORDS, tokens

NEAR_DUP_THRESHOLD = 0.90

WEIGHTS_WITH_BRIEF = {"relevance": 0.35, "quality": 0.20, "substance": 0.15, "richness": 0.10, "centrality": 0.20}
WEIGHTS_NO_BRIEF = {"quality": 0.30, "substance": 0.20, "richness": 0.15, "centrality": 0.35}


def mattr(toks: list[str], window: int = 500) -> float:
    """Moving-average type/token ratio: length-independent vocabulary diversity."""
    if len(toks) < window:
        return len(set(toks)) / max(len(toks), 1)
    step = window // 2
    ratios = [len(set(toks[i:i + window])) / window for i in range(0, len(toks) - window + 1, step)]
    return float(np.mean(ratios))


def text_quality(rec: dict) -> dict:
    text = rec["text"]
    n = max(len(text), 1)
    letters = sum(c.isalpha() for c in text)
    toks = tokens(text)
    words = text.split()
    # Garbled extraction shows up as many very long "words" or single-character fragments.
    odd = sum(1 for w in words if len(w) > 30 or (len(w) == 1 and not w.isalnum()))
    pages_with_text = sum(1 for p in rec["pages"] if len(p) >= 50)
    alpha_ratio = letters / n
    return {
        "words": len(toks),
        "pages": rec["n_pages"],
        "words_per_page": len(toks) / max(rec["n_pages"], 1),
        "alpha_ratio": round(alpha_ratio, 3),
        "garble_ratio": round(odd / max(len(words), 1), 4),
        "text_page_ratio": round(pages_with_text / max(rec["n_pages"], 1), 3),
        "quality": float(np.clip(
            0.5 * (pages_with_text / max(rec["n_pages"], 1))
            + 0.4 * min(alpha_ratio / 0.75, 1.0)          # ~75% letters is normal prose
            + 0.1 * (1 - min(odd / max(len(words), 1) * 20, 1.0)),
            0, 1)),
        "richness_raw": mattr(toks),
        "_tokens": toks,
    }


def minmax(s: pd.Series) -> pd.Series:
    lo, hi = s.min(), s.max()
    return (s - lo) / (hi - lo) if hi > lo else pd.Series(1.0, index=s.index)


def allocate(counts: dict, total: int) -> dict:
    """Split `total` slots across groups proportionally to counts, at least 1 per group."""
    if not counts:
        return {}
    total = min(total, sum(counts.values()))
    quota = {g: min(c, 1) for g, c in counts.items()}
    while sum(quota.values()) < total:
        g = max((g for g in counts if quota[g] < counts[g]),
                key=lambda g: counts[g] / sum(counts.values()) * total - quota[g])
        quota[g] += 1
    return quota


def mmr_select(scores: np.ndarray, sim: np.ndarray, k: int, lam: float = 0.7) -> list[int]:
    """Pick k items maximising lam*score - (1-lam)*max_similarity_to_already_picked."""
    chosen: list[int] = []
    candidates = list(range(len(scores)))
    while candidates and len(chosen) < k:
        def gain(i):
            red = max((sim[i, j] for j in chosen), default=0.0)
            return lam * scores[i] - (1 - lam) * red
        best = max(candidates, key=gain)
        chosen.append(best)
        candidates.remove(best)
        candidates = [c for c in candidates if sim[best, c] < NEAR_DUP_THRESHOLD]
    return chosen


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out_dir", type=Path)
    ap.add_argument("--brief", type=Path, help="text file describing your project / what the model should know")
    ap.add_argument("--select", type=int, default=20, help="size of the recommended core set")
    ap.add_argument("--topics", type=int, default=0, help="number of topics (0 = auto)")
    ap.add_argument("--diversity", type=float, default=0.3,
                    help="0 = rank purely by score, 1 = maximise topic spread (default 0.3)")
    ap.add_argument("--min-words", type=int, default=300, help="documents shorter than this are excluded")
    ap.add_argument("--stopwords", type=Path, help="extra stopword list, one per line (e.g. for non-English text)")
    args = ap.parse_args()

    recs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((args.out_dir / "texts").glob("*.json"))]
    if len(recs) < 2:
        raise SystemExit("Need at least 2 extracted documents. Run extract.py first.")

    rows = []
    for r in recs:
        q = text_quality(r)
        rows.append({"file": r["file"], "title": r["metadata"].get("title", ""),
                     "needs_ocr": r["needs_ocr"], "language": r.get("language", "unknown"), **q})
    df = pd.DataFrame(rows)
    docs = [" ".join(t) for t in df.pop("_tokens")]

    stop = set(ENGLISH_STOP_WORDS) | PERSIAN_STOPWORDS
    if args.stopwords:
        stop |= {w.strip().lower() for w in args.stopwords.read_text(encoding="utf-8").splitlines() if w.strip()}

    # --- representation: TF-IDF (unigrams + bigrams) reduced with LSA for semantic similarity
    # docs are already tokenised by textnorm.tokens (keeps ZWNJ inside Persian words), so just split
    tfidf = TfidfVectorizer(tokenizer=str.split, token_pattern=None, lowercase=False,
                            stop_words=list(stop), ngram_range=(1, 2), min_df=1 if len(docs) < 10 else 2,
                            max_df=0.9, sublinear_tf=True, max_features=50000)
    X = tfidf.fit_transform(docs)
    vocab = np.array(tfidf.get_feature_names_out())
    n_comp = max(2, min(100, len(docs) - 1, X.shape[1] - 1))
    lsa = TruncatedSVD(n_components=n_comp, random_state=0)
    Z = normalize(lsa.fit_transform(X))
    sim = cosine_similarity(Z)

    # --- keywords per document
    df["keywords"] = [", ".join(vocab[np.argsort(-X[i].toarray()[0])[:8]]) for i in range(X.shape[0])]

    # --- topics (NMF on TF-IDF)
    k = args.topics or int(np.clip(round(math.sqrt(len(docs))), 2, 20))
    nmf = NMF(n_components=k, random_state=0, init="nndsvda", max_iter=500)
    W = nmf.fit_transform(X)
    topic_terms = [", ".join(vocab[np.argsort(-comp)[:10]]) for comp in nmf.components_]
    df["topic"] = W.argmax(axis=1)
    df["topic_strength"] = (W.max(axis=1) / (W.sum(axis=1) + 1e-9)).round(3)

    # --- near duplicates
    dup_of = []
    for i in range(len(docs)):
        js = [j for j in range(len(docs)) if j != i and sim[i, j] >= NEAR_DUP_THRESHOLD]
        dup_of.append("; ".join(df.file[j] for j in js))
    df["near_duplicates"] = dup_of

    # --- scores
    df["substance"] = minmax(np.log1p(df.words))
    df["richness"] = minmax(df.richness_raw)
    # English and Persian documents share almost no vocabulary, so centrality and relevance are
    # scaled within each language group; otherwise the smaller language would always lose.
    groups = df.groupby("language").groups
    centrality = pd.Series(0.0, index=df.index)
    for lang, members in groups.items():
        m = np.asarray(members)
        sub = sim[np.ix_(m, m)]
        centrality[m] = (sub.sum(axis=1) - 1) / max(len(m) - 1, 1)
    df["centrality"] = 0.0
    for lang, members in groups.items():
        df.loc[members, "centrality"] = minmax(centrality[members])
    weights = WEIGHTS_NO_BRIEF
    if args.brief:
        brief = " ".join(tokens(args.brief.read_text(encoding="utf-8")))
        bz = normalize(lsa.transform(tfidf.transform([brief])))
        lexical = cosine_similarity(tfidf.transform([brief]), X)[0]
        semantic = cosine_similarity(bz, Z)[0]
        rel = pd.Series(0.5 * lexical + 0.5 * semantic, index=df.index)
        df["relevance"] = 0.0
        for lang, members in groups.items():
            df.loc[members, "relevance"] = minmax(rel[members])
        weights = WEIGHTS_WITH_BRIEF
    df["score"] = sum(w * df[c] for c, w in weights.items()).round(4)

    eligible = (~df.needs_ocr) & (df.words >= args.min_words) & (df.quality >= 0.5)
    df["excluded_reason"] = np.select(
        [df.needs_ocr, df.words < args.min_words, df.quality < 0.5],
        ["needs OCR", f"under {args.min_words} words", "poor text quality"], default="")

    # Core-set slots are shared out between languages in proportion to eligible documents
    # (at least one each), then filled per language with MMR.
    elig_by_lang = df[eligible].groupby("language").size()
    quota = allocate(elig_by_lang.to_dict(), args.select)
    picked = []
    for lang, n in quota.items():
        idx = np.flatnonzero((eligible & (df.language == lang)).values)
        picked += [idx[i] for i in mmr_select(df.score.values[idx], sim[np.ix_(idx, idx)], n, lam=1 - args.diversity)]
    picked.sort(key=lambda i: -df.score[i])
    df["selected"] = False
    df.loc[picked, "selected"] = True
    df["selection_rank"] = pd.Series({p: r + 1 for r, p in enumerate(picked)})

    # --- outputs
    cols = ["selection_rank", "selected", "file", "language", "title", "score", *weights.keys(), "words", "pages",
            "topic", "topic_strength", "keywords", "near_duplicates", "excluded_reason",
            "alpha_ratio", "garble_ratio", "text_page_ratio", "words_per_page"]
    df = df[cols].sort_values(["selected", "selection_rank", "score"], ascending=[False, True, False])
    df.to_csv(args.out_dir / "document_scores.csv", index=False)
    counts = df.topic.value_counts()
    sel_counts = df[df.selected].topic.value_counts()
    topics = pd.DataFrame({"topic": range(k), "top_terms": topic_terms,
                           "documents": [int(counts.get(t, 0)) for t in range(k)],
                           "in_core_set": [int(sel_counts.get(t, 0)) for t in range(k)]})
    topics.to_csv(args.out_dir / "topics.csv", index=False)
    write_report(args, df, topics, weights)
    print(f"Analysed {len(df)} documents, {int(eligible.sum())} eligible, {len(picked)} selected.")
    print(f"See {args.out_dir / 'report.md'}")


def write_report(args, df: pd.DataFrame, topics: pd.DataFrame, weights: dict) -> None:
    sel = df[df.selected]
    lines = [
        "# Document selection report", "",
        f"- Documents analysed: **{len(df)}**",
        f"- Recommended core set: **{len(sel)}** documents",
        "- Languages (all / core set): " + ", ".join(
            f"{lang} {n} / {int((sel.language == lang).sum())}" for lang, n in df.language.value_counts().items()),
        f"- Scoring weights: " + ", ".join(f"{k} {v:.0%}" for k, v in weights.items()),
        f"- Project brief used: {'yes (' + args.brief.name + ')' if args.brief else 'no — ranking is by quality and representativeness only'}",
        "", "## Recommended core set", "",
        "| # | File | Lang | Score | Topic | Words | Keywords |", "|---|---|---|---|---|---|---|",
    ]
    for _, r in sel.iterrows():
        lines.append(f"| {int(r.selection_rank)} | {r.file} | {r.language} | {r.score:.3f} | {r.topic} | {r.words:,} | {r.keywords} |")
    lines += ["", "## Topics found", "", "| Topic | Docs | In core set | Top terms |", "|---|---|---|---|"]
    for _, t in topics.iterrows():
        lines.append(f"| {t.topic} | {t.documents} | {t.in_core_set} | {t.top_terms} |")
    excl = df[df.excluded_reason != ""]
    if len(excl):
        lines += ["", "## Excluded", "", "| File | Reason |", "|---|---|"]
        lines += [f"| {r.file} | {r.excluded_reason} |" for _, r in excl.iterrows()]
    dups = df[(df.near_duplicates != "")]
    if len(dups):
        lines += ["", "## Near-duplicates (similarity ≥ 0.90)", ""]
        lines += [f"- {r.file} ≈ {r.near_duplicates}" for _, r in dups.iterrows()]
    (args.out_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
