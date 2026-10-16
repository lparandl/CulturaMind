# Pipeline: PDF extraction and core-set selection

    pip install -r requirements.txt
    python extract.py <pdf_dir> <out_dir> [--txt]
    python analyze.py <out_dir> [--brief brief.txt] [--select 20] [--diversity 0.3]

Or run `CulturaMind_pipeline.ipynb` in Google Colab on PDFs stored in Google Drive.

## Step 1 — `extract.py`
One JSON file per PDF in `<out_dir>/texts/` with page-by-page text, metadata, detected
language (`en` / `fa` / `mixed`) and flags; plus `extraction_summary.csv`.
- Removes running headers/footers and line-break hyphens.
- Persian clean-up (`textnorm.py`): Arabic ي/ك → ی/ک, presentation-form glyphs, diacritics,
  tatweel, bidi marks, Persian/Arabic digits; detects and fixes text stored in reversed order.
- Skips byte-identical duplicates; flags scanned PDFs (no text layer) as needing OCR.

## Step 2 — `analyze.py`
Scores each document on quality, substance, vocabulary richness, centrality and (with a brief)
relevance, finds topics, flags near-duplicates, and selects a diverse core set. English and
Persian are scored within their own language and core-set slots are shared between languages
in proportion to the number of usable documents. Write `brief.txt` in both languages so it can
match documents in each.

Outputs: `document_scores.csv`, `topics.csv`, `report.md`.
