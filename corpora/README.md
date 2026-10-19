# Corpora: Digital library of Persian cultural texts (Aim 1)

Source texts for the digital library, grouped by category. Each text has its own folder
with the PDF(s) and a README giving the translator, edition, page count, text layer and copyright status.

| Folder | Category |
| --- | --- |
| `religion/` | Religious texts |
| `philosophical-intellectual/` | Philosophical and intellectual texts |
| `mass-media/` | Mass media and literary works |

This repository is public. Only add texts that are in the public domain or openly licensed.
Keep in-copyright translations out of the repository.

Run the pipeline on one text folder, for example:

    python pipeline/extract.py corpora/religion/zend-avesta out --txt --ocr eng
