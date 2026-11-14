# Reference text and 10/18 edition alignment

The local text `bedier_reference.txt` is not included in the starter ZIP. Obtain the French **Joseph Bédier** text using:

```bash
python3 tools/fetch_reference.py
```

Verified source page: https://www.gutenberg.org/ebooks/42256
Direct French plain-text link: https://www.gutenberg.org/ebooks/42256.txt.utf-8
Alternative: https://fr.wikisource.org/wiki/Le_Roman_de_Tristan_et_Iseut

The reference and the 10/18 paperback are based on Bédier but can differ in pagination and small textual details. A print page number alone cannot identify a precise textual endpoint. `edition_page_map.csv` is intentionally blank: populate entries ONLY by checking the actual paperback. For every reading update, the parent supplies the exact final sentence, not a page. The tutor MUST run `python3 tools/align_reference.py --sentence '…'`, check the match and chapter in the reference, then persist the verbatim sentence and text offsets. If ambiguous or absent, request the previous sentence or a photo. Do not quiz beyond the last VERIFIED point.

Do not copy text from later chapters into learner-facing prompts, even as hints or metadata. Only provide excerpts up to the student's verified reading point.
