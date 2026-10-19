# Gathas: Zend-Avesta Part III (Mills) vs Azargoshasb

October 19, 2026. The outputs are in this folder. Script: [`compare_gathas.py`](../compare_gathas.py).

## Answer

**The two cover the same text but are different translations, so there is no duplicate to remove.** Zend-Avesta Part III (L. H. Mills, *Sacred Books of the East* 31, 1887) contains all 17 Gatha chapters. So does Azargoshasb's *Translation of Gathas*. Both have Yasna 28–34, 43–51 and 53. The wording, though, is almost entirely different. Across all 17 chapters the two translations share only 2 five-word sequences: "as long as I have" (Y. 43) and "I speak to you maidens" (Y. 53), where both translate the same line literally.

- **Same content:** for 15 of the 17 chapters, the closest match to a Mills chapter in Azargoshasb is the same chapter. The two exceptions are Yasna 43 and 50, which score slightly higher against Yasna 28 (by 0.02). My guess is that this is because Yasna 28 is a general prayer whose vocabulary turns up throughout the Gathas.
- **Different wording:** the similarity scores are low in absolute terms (median 0.06 per verse, 0.10–0.22 per chapter). That's because the translators word things very differently, even where they mean the same thing.
- **Complete in both:** Azargoshasb has 238 numbered verses, which matches the standard count. The parser recovered 218 of Mills' verses (see "Limits").

## How the translations differ

| | Mills (1887) | Azargoshasb (1988) |
|---|---|---|
| Translator | Western philologist, translating from Avestan with the Pahlavi commentary | Zoroastrian priest (mobed). His English follows his own simplified Persian translation |
| Style | Literal, archaic ("Thou", "aye"), with many parenthetical glosses | Plain modern English, interpretive, explaining as it goes ("Asha, the symbol of truthfulness and purity") |
| Extras | A long introduction to every chapter, plus footnotes on grammar and the Pahlavi | A short preface and a few footnotes |
| Order | Moves Yasna 29 before Yasna 28 | Manuscript order |
| Yasna 28 numbering | Counts the opening formula ("A strengthening blessing is the thought…") as verse 1 | Gives that formula unnumbered (the script shifts Mills to match) |

Example, Yasna 46.1. Zarathushtra describes being abandoned, which is directly relevant to social support and distress:

> **Mills:** To what land to turn; aye, whither turning shall I go? On the part of a kinsman (prince), or allied peer, none, to conciliate, give (offerings) to me (to help my cause), nor yet the throngs of labour, … nor yet (still less) the evil tyrants of the province.
>
> **Azargoshasb:** To what land shall I turn? Wither shall I turn for protection? My relatives have left me alone and my friends keep themselves apart from me. My co-workers bring no satisfaction for me. The rulers of the country are all inclined to untruth.

Example, Yasna 30.3, the "twin spirits" verse:

> **Mills:** Thus are the primeval spirits who as a pair (combining their opposite strivings), and (yet each) independent in his action, have been famed (of old). (They are) a better thing, they two, and a worse, as to thought, as to word, and as to deed. And between these two let the wisely acting choose aright.
>
> **Azargoshasb:** The twain spirits which appeared in the world of thought in the beginning were good and evil in thoughts, words and deeds. The wise will choose rightly (of the said two thoughts), but the unwise shall not do so and shall go astray.

**What this means for the library:** keep both. If the Zend-Avesta is analysed as a whole, its Gathas are already in the corpus through Part III. Counting Azargoshasb as well would weight the Gathas twice, so either analyse the Gathas as their own unit, or mark Azargoshasb as a parallel translation. Azargoshasb is a modern, devotional reading by an Iranian Zoroastrian priest, so it may be closer to how Persian Zoroastrians understand the text today. Mills is closer to the Avestan wording.

## Method

1. Text came from the existing `extract.py` output for Part III, and straight from the PDF for Azargoshasb. (`extract.py` drops Azargoshasb's "Verse N:" labels as repeated page headers.)
2. For Mills, each chapter's introduction (everything before "Translation.") was dropped, along with running headers, footnote blocks at the foot of each page, and footnote markers.
3. Both texts were split into chapters and verses, then aligned by Yasna chapter and verse number.
4. Similarity is TF-IDF cosine on one vocabulary fitted to both translations, after removing English stop words and archaic forms such as "thou", "thee" and "ye". Literal overlap is counted as shared five-word sequences.

## Limits

- **Mills' footnotes leak through.** Footnotes that continue from one page onto the next don't start with a number, so they aren't removed. About 33 Mills verses have notably more words than they should (see `verses.csv`). Mills' word counts are therefore inflated, and his verse-level scores are a little noisy. The chapter-level conclusion doesn't depend on this.
- **20 Mills verse numbers were not recovered,** because OCR misreads numbers at the start of a line (Y. 31.6, 12, 16, 18; Y. 32.1, 13; Y. 33.3; Y. 34.13; Y. 44.11, 12, 17, 18; Y. 46.12, 17; Y. 50.1; Y. 51.12; Y. 53.3). Their text is merged into the verse before, so it is still counted at chapter level.
- **Low similarity is not the same as disagreement.** Different wording of the same idea scores low. Reading the verses in `verses.csv` side by side is the real check.

## Files

- `chapters.csv`: per chapter, verse and word counts, same-chapter and best other-chapter similarity, and shared 5-grams.
- `verses.csv`: every aligned verse, with both translations side by side and their similarity.
- `similarity_matrix.csv`: Mills chapters × Azargoshasb chapters.
- `report.md`: the summary table printed by the script.
