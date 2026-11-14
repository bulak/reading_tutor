#!/usr/bin/env python3
"""Locate the final sentence a student has read in a local French reference.

Reports character offsets only; never returns text from after the reading boundary.
Exact token alignment tolerates accents, apostrophes, whitespace, and punctuation.
Fuzzy candidates need manual verification and are NEVER marked verified.
"""
import argparse
from collections import Counter, defaultdict
from difflib import SequenceMatcher
import json
from pathlib import Path
import re
import sys
import unicodedata

SOURCE = Path(__file__).resolve().parents[1] / 'sources' / 'bedier_reference.txt'
WORD = re.compile(r'[^\W_]+', flags=re.UNICODE)


def norm(word):
    word = unicodedata.normalize('NFKD', word.casefold())
    return ''.join(ch for ch in word if not unicodedata.combining(ch))


def words_with_offsets(txt):
    return [(norm(m.group()), m.start(), m.end()) for m in WORD.finditer(txt)]


def align(sentence, reference):
    needle = [w for w, _, _ in words_with_offsets(sentence)]
    corpus = words_with_offsets(reference)
    if not needle:
        raise ValueError('Please supply a nonempty last sentence.')
    nt = len(needle)
    ct = [x[0] for x in corpus]
    exact = []
    # First token narrows the search, avoiding quadratic scans.
    first = needle[0]
    for i, w in enumerate(ct):
        if w == first and ct[i:i + nt] == needle:
            exact.append({'start': corpus[i][1], 'end': corpus[i + nt - 1][2],
                          'line': reference.count('\n', 0, corpus[i][1]) + 1})
    if len(exact) == 1:
        return {'status': 'exact', 'verified': True, 'matches': exact, 'words': nt}
    if len(exact) > 1:
        return {'status': 'ambiguous', 'verified': False,
                'matches': exact[:12], 'total_matches': len(exact), 'words': nt,
                'action': 'Ask for the preceding sentence(s) to resolve repeated text.'}

    if nt < 5:
        return {'status': 'not_found', 'verified': False, 'words': nt,
                'action': 'Ask for preceding context or a photograph; short phrases cannot be matched fuzzily.'}

    # Suggest probable source loci but do NOT treat them as verified or store as the endpoint.
    occurrence = defaultdict(list)
    for pos, word in enumerate(ct):
        occurrence[word].append(pos)
    rare_words = sorted(set(needle), key=lambda w: len(occurrence.get(w, ())))[:6]
    votes = Counter()
    for w in rare_words:
        for pos in occurrence.get(w, ())[:800]:
            for index, nw in enumerate(needle):
                if nw == w:
                    start = pos - index
                    if 0 <= start <= len(ct) - nt:
                        votes[start] += 1
    scored = []
    target = ' '.join(needle)
    for start, _ in votes.most_common(120):
        for delta in (-2, -1, 0, 1, 2):
            i = start + delta
            if 0 <= i <= len(ct) - nt:
                window = ' '.join(ct[i:i + nt])
                ratio = SequenceMatcher(None, target, window, autojunk=False).ratio()
                scored.append((ratio, i))
    scored.sort(reverse=True)
    dedup = []
    for ratio, i in scored:
        if any(abs(i - prior) < nt for _, prior in dedup):
            continue
        dedup.append((ratio, i))
        if len(dedup) >= 3:
            break
    return {'status': 'approximate' if dedup and dedup[0][0] >= 0.82 else 'not_found',
            'verified': False, 'words': nt,
            'candidates': [{'similarity': round(score, 3), 'start': corpus[i][1],
                            'end': corpus[i + nt - 1][2],
                            'line': reference.count('\n', 0, corpus[i][1]) + 1}
                           for score, i in dedup if score >= 0.6],
            'action': 'Compare the suggested passage in the source with the actual 10/18 text. Ask for preceding sentence(s) or a photo if uncertain. NEVER record a fuzzy candidate as exact.'}


def main():
    parser = argparse.ArgumentParser(description='Locate an exact final sentence in Bédier reference')
    parser.add_argument('--sentence', required=True, help='Verbatim last sentence read in French')
    args = parser.parse_args()
    if not SOURCE.exists():
        raise ValueError('Reference missing. Run python3 tools/fetch_reference.py first.')
    print(json.dumps(align(args.sentence, SOURCE.read_text(encoding='utf-8-sig')),
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(2)
