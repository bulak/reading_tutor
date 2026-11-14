# Tristan et Iseut — local Hermes reading tutor

A **stateless-session** French reading tutor for Joseph Bédier's *Le Roman de Tristan et Iseut* (10/18 printing). The local files, rather than model memory or a long-lived conversation, track reading checkpoints, every question, student answers, assessments, and later revision priorities.

## 1. Initial setup

Unzip or copy this folder onto the computer that runs Hermes. In a terminal:

```bash
cd /path/to/tristan-hermes
python3 tools/fetch_reference.py
hermes chat
```

The text download is recommended but optional. Hermes reads `AGENTS.md` automatically **when launched from this directory**. The command `python3 tools/tracker.py status` shows the same learning snapshot that Hermes will use. Requires **Python 3.9+**, using only its standard library; no third-party Python packages. The Gutenberg text is downloaded on your own machine, not packaged in this archive.

If your Hermes terminal tools are sandboxed via Docker or SSH, ensure **this folder is writable and visible inside that environment**; otherwise writes will not persist locally. For a local backend, launching from the folder is generally sufficient. See official Hermes context file documentation: https://hermes-agent.nousresearch.com/docs/user-guide/features/context-files

## 2. First checkpoint — use the last sentence, never a page number

You (the parent) speak **English** to Hermes. Hermes asks your son the reading-comprehension questions in **French**. Example:

> I'm the parent. My son has read up to this exact sentence: «...». Please align that sentence with the local French reference **before** recording the reading checkpoint or asking any questions. Then conduct a short quiz in French, without spoilers.

Hermes must first run `tools/align_reference.py` on that sentence, locate the matching reference passage, confirm which chapter the match is in, and record the **verbatim sentence plus reference-text offsets** through `tools/tracker.py`. If there are multiple matches or no reliable match, it must ask for a preceding sentence or a photo, not guess.

The match can also be checked manually:

```bash
python3 tools/align_reference.py --sentence "Copy the exact French last sentence here"
```

If alignment remains uncertain, Hermes may still quiz **previously verified, fully read chapters**, but must not quiz the unverified partial chapter. Neither printed pages nor their correspondence with Gutenberg are needed.

## 3. Subsequent sessions

Run `hermes chat` again from this folder. Tell Hermes, for example:

> My son has now read up to: «...». Please verify this sentence in the reference, save his progress, and quiz him in French for ten minutes.

Or ask as parent:

> Give me a summary of his previous answers, strengths, and the topics that need to be revisited.

Hermes should read the event log and current snapshots each time, resume unfinished questions, ask one question at a time, log the student's exact answers, and produce a session report after closing.

## 4. Folder layout

```
AGENTS.md                      Hermes tutor rules, read on launch
README.md                      Instructions for the parent
sources/README.md             Reference text and printing caveats
sources/bedier_reference.txt  Downloaded by fetch_reference.py; not included yet
sources/edition_page_map.csv  Legacy optional page map; not used for this workflow
sources/book.json             Edition and source metadata

data/events.jsonl             Append-only, authoritative learning history
data/progress.json           Rebuilt reading/sessions/question snapshot
data/mastery.json            Rebuilt topic-level evidence and review priorities

reports/S0001.md               Generated after first closed assessment
reports/S0002.md               Generated after second, etc.
tools/tracker.py               Validate, read and update all learning history
tools/align_reference.py       Verify the final sentence and locate it in the local text
tools/fetch_reference.py       Fetch public-domain Joseph Bédier text
```

`events.jsonl` starts empty, and progress/mastery with empty state. The `tracker.py` script regenerates the snapshots after every event, so they cannot drift apart if its commands are used consistently. The generated reports contain question/answer text that is deliberately NOT stored only inside a transient conversation.

## 5. Data discipline

- Keep student identity, full name and other unnecessary personal details **out of the logs**. Back up the folder privately.
- **Do not hand-edit** `events.jsonl`, `progress.json`, or `mastery.json`. Hermes updates these via `tools/tracker.py` only.
- One process writes to this folder at a time. It is a simple local tool, not a multi-user database.
- If a session is interrupted, `python3 tools/tracker.py status` identifies the pending question. Resume it before moving on.
- The scores are estimates of understanding, not school grades or psychological assessments. Corrections are permitted; older answers are preserved for comparison.
- The public-domain reference may have spelling/punctuation differences compared with the 10/18 printing. Never invent a printed edition's page number or fabricate a quotation. If the last-sentence matcher suggests a fuzzy match, **manually verify it**, or treat the endpoint as unverified. The matcher returns reference offsets and does **not** grant permission to use future text.

## 6. Helpful checks

```bash
python3 tools/tracker.py status     # View current reading level and weak topics
python3 tools/tracker.py validate   # Check history and regenerate snapshots
```

The book has 19 chapters. When the parent confirms completion, Hermes can build a final practice examination based on the complete answer history, including revisiting past misconceptions.

## Key external reference

Joseph Bédier, *Le roman de Tristan et Iseut*, French text, Project Gutenberg eBook 42256:
https://www.gutenberg.org/ebooks/42256

This is the same Bédier adaptation, **not a guarantee of exact formatting or page numbering** in the 10/18 paperback.
