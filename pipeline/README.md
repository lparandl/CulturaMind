# Pipeline: PDF extraction, validation and core-set selection

    pip install -r requirements.txt
    # OCR for scanned PDFs needs Tesseract: apt-get install tesseract-ocr tesseract-ocr-fas
    python extract.py  <pdf_dir> <out_dir> [--txt] [--ocr eng+fas]
    python validate.py <pdf_dir> <out_dir> [--wordlist words.txt] [--reference notebook_txt_dir]
    python chunk.py    <out_dir> <passage_dir> [--words 1500]          # optional
    python analyze.py  <passage_dir or out_dir> [--brief brief.txt] [--select 20] [--diversity 0.3]

`compare_gathas.py` compares two translations of the Gathas verse by verse (see `docs/gathas-comparison.md`).

Or run `CulturaMind_pipeline.ipynb` in Google Colab on PDFs stored in Google Drive.
A full worked example on the three Zend-Avesta volumes is in `docs/zend-avesta-report.md`,
with its outputs in `outputs/zend-avesta/`.

## Step 1 — `extract.py`
One JSON file per PDF in `<out_dir>/texts/` with page-by-page text, metadata, detected
language (`en` / `fa` / `mixed`) and flags; plus `extraction_summary.csv`.
- `--ocr`: pages without a text layer (scans) are read with Tesseract, in parallel.
- Removes running headers/footers and re-joins words hyphenated across lines.
- Persian clean-up (`textnorm.py`): Arabic ي/ك → ی/ک, presentation-form glyphs, diacritics,
  tatweel, bidi marks, Persian/Arabic digits; detects and fixes text stored in reversed order.
- Skips byte-identical duplicates; flags scanned PDFs that were not OCR'd.

## Step 2 — `validate.py`
Checks extraction before any analysis is trusted. Writes `<out_dir>/validation/`:
- `page_quality.csv`: per page — type (body, front/back matter, index, publisher catalogue,
  blank), valid-word rate, noise rate, flag.
- `summary.csv`: per document, plus word overlap with another extractor (`--reference`).
- `review.html`: random body pages, page image beside extracted text, for a person to check.
  Record results in `manual_check.csv` (file, page, words_checked, word_errors).

## Step 3 — `chunk.py` (optional)
Splits documents into ~1,500-word passages so books can be ranked section by section. Skips
non-body pages and pages flagged by `validate.py`.

## Step 4 — `analyze.py`
Scores each document or passage on quality, substance, vocabulary richness, centrality and
(with a brief) relevance, finds topics, flags near-duplicates, and selects a diverse core set.
English and Persian are scored within their own language and core-set slots are shared between
languages in proportion to the number of usable documents. Write `brief.txt` in both languages.

Outputs: `document_scores.csv`, `topics.csv`, `report.md`.
