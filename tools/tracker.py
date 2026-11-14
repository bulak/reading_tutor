#!/usr/bin/env python3
"""File-based, append-only reading tutor tracker. Python 3.9+, standard library.

The event ledger is authoritative. progress.json and mastery.json are rebuilt
from the ledger, so starting a new agent session needs no chat history.
"""
import argparse
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from statistics import mean
from align_reference import words_with_offsets

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
EVENTS = DATA / 'events.jsonl'
PROGRESS = DATA / 'progress.json'
MASTERY = DATA / 'mastery.json'
REPORTS = ROOT / 'reports'
TOTAL_CHAPTERS = 19


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def load_events():
    if not EVENTS.exists():
        return []
    events = []
    with EVENTS.open(encoding='utf-8') as f:
        for lineno, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
                if not isinstance(item, dict) or 'kind' not in item:
                    raise ValueError('not an event')
                events.append(item)
            except (ValueError, json.JSONDecodeError) as e:
                raise ValueError(f'Corrupt history at {EVENTS}:{lineno}: {e}') from e
    return events


def atom_write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    with tmp.open('w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def append_event(event):
    DATA.mkdir(parents=True, exist_ok=True)
    event = {'time': now(), **event}
    line = json.dumps(event, ensure_ascii=False, separators=(',', ':')) + '\n'
    with EVENTS.open('a', encoding='utf-8') as f:
        f.write(line)
        f.flush()
        os.fsync(f.fileno())
    rebuild(load_events())
    return event


def summarize(events):
    position = {'completed_through': 0, 'current_chapter': None, 'current_page': None,
                'last_sentence': '', 'alignment': 'unverified',
                'reference_start': None, 'reference_end': None,
                'reading_note': '', 'updated_at': None}
    sessions = {}
    questions = {}
    for e in events:
        kind = e['kind']
        if kind == 'checkpoint':
            position.update({
                'completed_through': e['completed_through'],
                'current_chapter': e.get('current_chapter'),
                'current_page': e.get('current_page'),
                'last_sentence': e.get('last_sentence', ''),
                'alignment': e.get('alignment', 'unverified'),
                'reference_start': e.get('reference_start'),
                'reference_end': e.get('reference_end'),
                'reading_note': e.get('note', ''),
                'updated_at': e['time']
            })
        elif kind == 'session_start':
            sessions[e['session_id']] = {'started_at': e['time'], 'ended_at': None,
                                         'summary': '', 'question_ids': []}
        elif kind == 'question_asked':
            questions[e['question_id']] = {'question_id': e['question_id'],
                'session_id': e['session_id'], 'question': e['question'],
                'scope': e['scope'], 'topics': e.get('topics', []),
                'anchor': e.get('anchor', ''), 'asked_at': e['time'],
                'answers': [], 'score': None, 'hinted': None, 'feedback': None,
                'evaluated_at': None}
            sessions[e['session_id']]['question_ids'].append(e['question_id'])
        elif kind == 'student_answer':
            questions[e['question_id']]['answers'].append({'text': e['text'], 'time': e['time']})
        elif kind == 'evaluation':
            q = questions[e['question_id']]
            q.update({'score': e['score'], 'hinted': e['hinted'],
                      'feedback': e['feedback'], 'evaluated_at': e['time']})
        elif kind == 'session_end':
            sessions[e['session_id']]['ended_at'] = e['time']
            sessions[e['session_id']]['summary'] = e.get('summary', '')
    mastery = {}
    for q in questions.values():
        if q['score'] is None:
            continue
        for topic in q['topics']:
            t = mastery.setdefault(topic, {'attempts': 0, 'scores': [], 'last_at': None,
                                          'last_question_id': None})
            t['attempts'] += 1
            t['scores'].append(q['score'])
            t['last_at'] = q['evaluated_at']
            t['last_question_id'] = q['question_id']
    for entry in mastery.values():
        nums = entry.pop('scores')
        entry['mean_score'] = round(mean(nums), 2)
        entry['recent_mean_score'] = round(mean(nums[-3:]), 2)
        entry['last_score'] = nums[-1]
        entry['needs_review'] = entry['recent_mean_score'] < 1.5 or entry['last_score'] < 2
    open_questions = [q['question_id'] for q in questions.values() if q['score'] is None]
    recent = list(questions.values())[-12:]
    progress = {
        'schema_version': 1, 'book': 'Joseph Bédier, Le Roman de Tristan et Iseut',
        'total_chapters': TOTAL_CHAPTERS, 'reading_position': position,
        'sessions_total': len(sessions),
        'sessions_completed': sum(bool(s['ended_at']) for s in sessions.values()),
        'questions_total': len(questions),
        'questions_evaluated': sum(q['score'] is not None for q in questions.values()),
        'open_question_ids': open_questions,
        'active_session_ids': [sid for sid, session in sessions.items() if not session['ended_at']],
        'recent_questions': [dict({k: q[k] for k in ('question_id','session_id','question','scope','topics','score','hinted')},
                                  last_answer=q['answers'][-1]['text'] if q['answers'] else None)
                             for q in recent],
        'last_session_id': next(reversed(sessions), None) if sessions else None,
        'history_file': 'data/events.jsonl'
    }
    mastery_snapshot = {'schema_version': 1, 'topics': mastery,
                        'review_first': sorted([k for k, v in mastery.items() if v['needs_review']],
                                               key=lambda k: (mastery[k]['recent_mean_score'],
                                                              mastery[k]['last_at'] or ''))}
    return progress, mastery_snapshot, questions, sessions


def rebuild(events):
    progress, mastery, _, _ = summarize(events)
    atom_write(PROGRESS, progress)
    atom_write(MASTERY, mastery)
    return progress, mastery


def require_session(sessions, sid):
    if sid not in sessions:
        raise ValueError(f'Unknown session: {sid}')
    if sessions[sid]['ended_at']:
        raise ValueError(f'Session is already closed: {sid}')


def require_question(questions, qid):
    if qid not in questions:
        raise ValueError(f'Unknown question: {qid}')
    if questions[qid]['score'] is not None:
        raise ValueError(f'Question already evaluated: {qid}')
    return questions[qid]


def make_report(sid, progress, mastery, questions, sessions):
    s = sessions[sid]
    lines = [f'# Session report — {sid}', '',
             f"Date (UTC): {s['started_at']}", '',
             f"Reading position: completed chapters through {progress['reading_position']['completed_through']}; "
             f"current chapter: {progress['reading_position']['current_chapter'] or 'unknown'}; "
             f"Last sentence read: {progress['reading_position'].get('last_sentence') or '(not supplied)'}", 
             f"Reference alignment: {progress['reading_position'].get('alignment', 'unverified')}", '',
             '## Questions and answers', '']
    for qid in s['question_ids']:
        q = questions[qid]
        lines.extend([f"### {qid} — {q['scope']} ({', '.join(q['topics'])})",
                      f"Question: {q['question']}",
                      f"Student answer(s): {' | '.join(a['text'] for a in q['answers']) or '(none)'}",
                      f"Score: {q['score'] if q['score'] is not None else 'not assessed'} / 2",
                      f"Hints: {'yes' if q['hinted'] else 'no' if q['hinted'] is False else 'unknown'}",
                      f"Feedback: {q['feedback'] or '(none)'}", ''])
    lines.extend(['## Summary', '', s['summary'] or '(none)', '', '## Topics to revisit', '',
                  ', '.join(mastery['review_first']) or '(no weak topics identified)', ''])
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / f'{sid}.md').write_text('\n'.join(lines), encoding='utf-8')


def main():
    p = argparse.ArgumentParser(description='Append-only local tutor history, no dependencies')
    sp = p.add_subparsers(dest='cmd', required=True)
    sp.add_parser('status', help='Read computed progress, weak topics and recent questions')
    sp.add_parser('validate', help='Parse event log and rebuild derived files')
    ck = sp.add_parser('checkpoint', help='Confirmed reading position; only completed chapters are quiz-safe by default')
    ck.add_argument('--completed-through', type=int, required=True)
    ck.add_argument('--current-chapter', type=int)
    ck.add_argument('--page', type=int, help='Legacy optional note; not used as reading boundary')
    ck.add_argument('--last-sentence', default='', help='Verbatim last sentence read; preferred endpoint marker')
    ck.add_argument('--alignment', choices=('exact', 'unverified'), default='unverified',
                    help='exact is confirmed only when source offsets genuinely match the sentence')
    ck.add_argument('--reference-start', type=int, help='Zero-based start character offset in local source')
    ck.add_argument('--reference-end', type=int, help='Exclusive end character offset in local source')
    ck.add_argument('--note', default='')
    sp.add_parser('start', help='Start a new assessment session, prints session ID')
    ask = sp.add_parser('ask', help='Log a question BEFORE displaying it to the student')
    ask.add_argument('--session', required=True)
    ask.add_argument('--scope', required=True, help='e.g. I or I-III')
    ask.add_argument('--topics', required=True, help='Comma-separated stable names, e.g. personnages,causalite')
    ask.add_argument('--question', required=True)
    ask.add_argument('--anchor', default='', help='Verified chapter or passage; never invent page numbers')
    ans = sp.add_parser('answer', help='Log student response verbatim; may call multiple times per question')
    ans.add_argument('--id', required=True)
    ans.add_argument('--text', required=True)
    ev = sp.add_parser('grade', help='Assess question after answers, 0=no, 1=partial/with help, 2=independent')
    ev.add_argument('--id', required=True)
    ev.add_argument('--score', type=int, choices=(0,1,2), required=True)
    ev.add_argument('--hinted', choices=('yes','no'), required=True)
    ev.add_argument('--feedback', required=True)
    end = sp.add_parser('end', help='Close session and write a session report')
    end.add_argument('--session', required=True)
    end.add_argument('--summary', required=True)
    a = p.parse_args()
    events = load_events()
    progress, mastery, questions, sessions = summarize(events)
    if a.cmd in ('status', 'validate'):
        if a.cmd == 'validate':
            rebuild(events)
        print(json.dumps({'progress': progress, 'mastery': mastery}, ensure_ascii=False, indent=2))
        return
    if a.cmd == 'checkpoint':
        if not 0 <= a.completed_through <= TOTAL_CHAPTERS:
            raise ValueError('completed-through must be between 0 and 19')
        if a.current_chapter is not None and not (1 <= a.current_chapter <= TOTAL_CHAPTERS):
            raise ValueError('current-chapter must be between 1 and 19')
        if a.current_chapter is not None and a.current_chapter <= a.completed_through:
            raise ValueError('current-chapter must be AFTER completed-through')
        if a.page is not None and a.page < 1:
            raise ValueError('page must be positive')
        if a.completed_through == TOTAL_CHAPTERS and a.current_chapter is not None:
            raise ValueError('Book complete: current chapter must be unset')
        if a.current_chapter is not None and not a.last_sentence.strip():
            raise ValueError('Supply the exact last sentence for a partially read chapter')
        if a.alignment == 'exact':
            source = ROOT / 'sources' / 'bedier_reference.txt'
            if not a.last_sentence.strip() or not source.exists():
                raise ValueError('Exact alignment requires last sentence and downloaded reference')
            if a.reference_start is None or a.reference_end is None:
                raise ValueError('Exact alignment requires verified reference start/end offsets')
            txt = source.read_text(encoding='utf-8-sig')
            if not (0 <= a.reference_start < a.reference_end <= len(txt)):
                raise ValueError('Invalid source offsets')
            normalize = lambda val: [w for w, _, _ in words_with_offsets(val)]
            if normalize(txt[a.reference_start:a.reference_end]) != normalize(a.last_sentence):
                raise ValueError('Reference at supplied offsets does not match last sentence')
        elif a.reference_start is not None or a.reference_end is not None:
            raise ValueError('Unverified checkpoints must NOT contain source offsets')
        if a.alignment == 'unverified' and a.completed_through > progress['reading_position']['completed_through']:
            raise ValueError('Unverified checkpoint cannot advance completed-chapter boundary; verify sentence first')
        append_event({'kind': 'checkpoint', 'completed_through': a.completed_through,
                      'current_chapter': a.current_chapter, 'current_page': a.page,
                      'last_sentence': a.last_sentence, 'alignment': a.alignment,
                      'reference_start': a.reference_start, 'reference_end': a.reference_end,
                      'note': a.note})
        print('Reading checkpoint saved.')
    elif a.cmd == 'start':
        pending = [sid for sid, session in sessions.items() if not session['ended_at']]
        if pending:
            raise ValueError(f'Open session exists: {pending}. Resume or close it before starting a new session')
        # Sequential ID avoids confusing identical-second session starts.
        sid = f'S{len(sessions)+1:04d}'
        append_event({'kind': 'session_start', 'session_id': sid})
        print(sid)
    elif a.cmd == 'ask':
        require_session(sessions, a.session)
        if any(q['score'] is None for q in questions.values()):
            raise ValueError('An unanswered/unevaluated question exists; resume it before asking another')
        tags = list(dict.fromkeys(x.strip().lower() for x in a.topics.split(',') if x.strip()))
        if not tags:
            raise ValueError('Provide at least one topic')
        qid = f'Q{len(questions)+1:05d}'
        append_event({'kind':'question_asked', 'question_id':qid,'session_id':a.session,
                      'scope':a.scope,'topics':tags,'question':a.question,'anchor':a.anchor})
        print(qid)
    elif a.cmd == 'answer':
        q = require_question(questions, a.id)
        require_session(sessions, q['session_id'])
        if not a.text.strip():
            raise ValueError('Cannot log empty answer')
        append_event({'kind': 'student_answer', 'question_id': a.id, 'text': a.text})
        print('Answer recorded.')
    elif a.cmd == 'grade':
        q = require_question(questions, a.id)
        require_session(sessions, q['session_id'])
        if not q['answers']:
            raise ValueError('Cannot grade before recording student answer')
        if a.hinted == 'yes' and a.score == 2:
            raise ValueError('2 means independently understood; with hints score 0 or 1')
        append_event({'kind':'evaluation', 'question_id':a.id, 'score':a.score,
                      'hinted':a.hinted == 'yes','feedback':a.feedback})
        print('Evaluation recorded.')
    elif a.cmd == 'end':
        require_session(sessions, a.session)
        if any(q['score'] is None for q in questions.values() if q['session_id'] == a.session):
            raise ValueError('Unevaluated question in session; grade it before closing')
        append_event({'kind':'session_end','session_id':a.session,'summary':a.summary})
        progress, mastery, questions, sessions = summarize(load_events())
        make_report(a.session, progress, mastery, questions, sessions)
        print(f'Session closed. Report: reports/{a.session}.md')

if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError) as exc:
        import sys
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(2)
