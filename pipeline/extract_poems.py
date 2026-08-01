#!/usr/bin/env python3
"""Extract every transbliteration from the book .docx, preserving indentation.

  python pipeline/extract_poems.py [pipeline/inbox/book.docx] [-o pipeline/poems.json]

Indentation in the book is a mix of literal tabs and w:ind paragraph offsets
(left / firstLine, in twips; one tab stop = 720). Each is normalized to leading
"\t" characters. Stanza breaks (empty paragraphs inside a poem) are kept as
empty strings. Output:

  {"001": {"roman": "I", "part": "Part I. Sensing", "lines": ["...", "\t..."]}}
"""
import argparse
import json
import re
import zipfile
import xml.etree.ElementTree as ET

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
TAB_TWIPS = 720
HEADING = re.compile(r'^([IVXLC]+)\.\s*Transbliterat\w*\s*\((\d{3})\)\s*$')
PART = re.compile(r'^(Part\s+[IVXLC]+\.\s*\w[\w\s]*?)\s*$')
NOISE = re.compile(r'^\[-?\d+\]$')  # e.g. the [-841] version markers


def para_line(p):
    """Paragraph -> poem line with leading tabs, or None if not text."""
    text = ''.join(t.text or '' for t in p.iter(W + 't')).rstrip()
    ind = p.find(f'.//{W}ind')
    twips = 0
    if ind is not None:
        twips = int(ind.get(W + 'left') or 0) + int(ind.get(W + 'firstLine') or 0)
    tabs = round(twips / TAB_TWIPS) + len(p.findall(f'.//{W}tab'))
    return '\t' * tabs + text.lstrip('\t') if text else ''


def extract(docx_path):
    root = ET.fromstring(zipfile.ZipFile(docx_path).read('word/document.xml'))
    poems, current, part = {}, None, ''
    for p in root.iter(W + 'p'):
        raw = ''.join(t.text or '' for t in p.iter(W + 't')).strip()
        if PART.match(raw):
            part = PART.match(raw).group(1)
            current = None
            continue
        m = HEADING.match(raw)
        if m:
            current = {'roman': m.group(1), 'part': part, 'lines': []}
            poems[m.group(2)] = current
            continue
        if current is None or NOISE.match(raw):
            continue
        current['lines'].append(para_line(p))
    for poem in poems.values():  # trim surrounding blank lines
        lines = poem['lines']
        while lines and not lines[0]:
            lines.pop(0)
        while lines and not lines[-1]:
            lines.pop()
    return poems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('docx', nargs='?', default='pipeline/inbox/book.docx')
    ap.add_argument('-o', '--out', default='pipeline/poems.json')
    args = ap.parse_args()
    poems = extract(args.docx)
    with open(args.out, 'w') as f:
        json.dump(poems, f, indent=1, ensure_ascii=False)
    print(f"extracted {len(poems)} poems -> {args.out}")


if __name__ == '__main__':
    main()
