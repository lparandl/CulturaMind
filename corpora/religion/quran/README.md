# The Qur'an, verse by verse (Arabic with English translation)

| File | Rows | Columns | English translation |
| --- | --- | --- | --- |
| Dataset-Verse-by-Verse.xlsx | 6,236 verses (all 114 surahs) | 16 | Abdullah Yusuf Ali |

Columns: `SrNo`, `Juz`, `JuzNameArabic`, `JuzNameEnglish`, `SurahNo`, `SurahNameArabic`,
`SurahNameEnglish`, `SurahMeaning`, `WebLink` (quran.com link for the verse), `Classification`
(Makki / Medani), `AyahNo`, `EnglishTranslation`, `OrignalArabicText` (with diacritics; the column
name is misspelled in the source), `ArabicText` (without diacritics), `ArabicWordCount`, `ArabicLetterCount`.

## Source

Most likely **"The Quran Dataset" on Kaggle, by user `imrankhan197`**:
https://www.kaggle.com/datasets/imrankhan197/the-quran-dataset
("Entire Quran with English Translation. All the Ayats in Arabic and English."; around September 2021).

A search for these exact column names leads to that dataset. Its public Kaggle page could not be
read in full from this environment, so the owner, license and version still need confirming on the
Kaggle page. Parand obtained the file through an earlier study, and the copy here was last saved in
Excel on 2026-09-09.

The English is Yusuf Ali's translation (checked against 1:2, 2:255, 94:5 and 112:1). The Kaggle page
doesn't say which edition. The original 1934–38 text and later revised editions differ, and the
revised editions are in copyright.

## Notes on the data

- No verses or translations are missing.
- `Classification` has 7 unexpected values besides Makki (4,479) and Medani (1,750): `Middle` (6)
  and `Juhfa` (1), e.g. 22:52 is `Middle`. They look like traditional notes on where a verse was revealed (my reading). Check them before using the column.
