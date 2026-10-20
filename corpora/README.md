# Corpora: Digital library of Persian cultural texts

Source texts for the digital library, grouped by category. Each text has its own folder
with the PDF(s) and a README giving the translator, edition, page count, text layer and copyright status.

| Folder | Category |
| --- | --- |
| `religion/` | Religious texts |
| `philosophical-intellectual/` | Philosophical and intellectual texts |
| `mass-media/` | Mass media and literary works |


Run the pipeline on one text folder, for example:

    python pipeline/extract.py corpora/religion/zend-avesta out --txt --ocr eng
