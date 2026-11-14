#!/usr/bin/env python3
"""Download Bédier's French text from Project Gutenberg (one-time setup)."""
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError

BASE = Path(__file__).resolve().parents[1]
TARGET = BASE / 'sources' / 'bedier_reference.txt'
URLS = [
    'https://www.gutenberg.org/ebooks/42256.txt.utf-8',
    'https://www.gutenberg.org/cache/epub/42256/pg42256.txt',
]


def main():
    for url in URLS:
        try:
            req = Request(url, headers={'User-Agent':'Mozilla/5.0 (Reading tutor project; non-commercial educational use)'})
            with urlopen(req, timeout=25) as r:
                body = r.read()
            content = body.decode('utf-8-sig')
            if not (len(content) > 90000 and 'Joseph Bédier' in content and
                    'LES ENFANCES DE TRISTAN' in content.upper()):
                raise ValueError('Downloaded file does not resemble the expected Bédier text')
            TARGET.write_text(content, encoding='utf-8')
            print(f'Saved French reference: {TARGET} ({len(content):,} characters)')
            return
        except (URLError, ValueError, UnicodeError, OSError) as exc:
            print(f'Could not fetch from {url}: {exc}')
    raise SystemExit('Download failed. Open https://www.gutenberg.org/ebooks/42256 '
                     'and save the French Plain Text file manually to sources/bedier_reference.txt')

if __name__ == '__main__':
    main()
