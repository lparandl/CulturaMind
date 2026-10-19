# The Gathas of Zarathushtra (Azargoshasb translation)

| File | Pages | Text layer | Translator |
| --- | --- | --- | --- |
| Translation of Gathas - The Holy Songs Of Zarathushtra (Azargoshasb).pdf | 43 | Yes (born-digital) | Mobed Firouz Azargoshasb |

All 17 Gatha chapters (Yasna 28–34, 43–51, 53) with 238 numbered verses, in English. The English
follows Azargoshasb's simplified Persian translation (his preface is dated 1980). This electronic
version comes from the 1988 printing by the Council of Iranian Mobeds of North America and is
distributed by www.Zarathushtra.com.

**Terms (from the PDF):** "feel free to copy, reproduce, or duplicate any part or all of this
document for personal and scholarly purposes only, giving full credit to [the] translator and source.
No part of this publication may be reproduced in any form for commercial purposes." It is not in
the public domain. Keep this credit with the file, and do not use it commercially.

The same chapters, in L. H. Mills' 1887 translation, are in `../zend-avesta/` Part III.
`comparison/README.md` compares the two. The script is `compare_gathas.py` in this folder, and its outputs are in `comparison/`.

Reproduce:

    python pipeline/extract.py corpora/religion/gathas outputs/gathas --txt
    python corpora/religion/gathas/compare_gathas.py "outputs/zend-avesta/texts/Zend-Avesta Part III - Yasna, Visparad, Afrinagan, Gahs.json" "corpora/religion/gathas/Translation of Gathas - The Holy Songs Of Zarathushtra (Azargoshasb).pdf" corpora/religion/gathas/comparison
