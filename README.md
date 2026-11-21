<p align="center"><img src="assets/banner.png" alt="SilenceProof: check whether the supplied records support an inbox read without a recorded wake." width="100%"></p>

<p align="center">
<img src="https://img.shields.io/badge/license-MIT-F2B544?style=flat-square" alt="MIT licence">
<img src="https://img.shields.io/badge/python-3-F2B544?style=flat-square" alt="Python 3">
<img src="https://img.shields.io/badge/built%20by-AI%20agents-F4EFE6?style=flat-square&labelColor=0D1821" alt="Built by AI agents">
</p>

**Check whether the supplied records support an inbox read without a recorded wake.**

An agent says: "I got message 10 by checking my inbox. Nobody had to wake me." That's a claim about something that *didn't* happen, and those are easy to make and hard to check. Maybe the agent really did read it. Or maybe its checker stopped, restarted, skipped a page, and the message only turned up by luck. SilenceProof can assess the supplied page chain.

SilenceProof reads one saved record file (the send receipt, the inbox checks, any wake or restart) and prints one verdict:

- **COVERED**: the matching inbox checks' page markers join up with no missing page, the closing check finishes at the deadline (written exactly as the deadline is written), one of those checks returned the message, and no wake was recorded for that message. Only polls for that recipient and session count toward page coverage. No such check may start before the message was accepted: one that starts earlier prints NOT COVERED. A restart is checked against the poll records on either side in file order, and an unexplained restart is a gap. COVERED does not mean the checks started the moment the message was accepted, or that the time between checks was watched: a check that starts later, or two checks with a gap in time between them, can still print COVERED when their page markers join.
- **NOT COVERED**: something is missing or doesn't add up, including an unexplained restart, so the claim can't be backed by these records. This is never treated as success. The line does not say which gap it was.
- **REJECTED**: two separate reasons. The records show a recorded wake for that message, so the claim is false. Or the records are unusable evidence. Unusable evidence does not mean the claim is false: the file has a record the checker cannot read. Types must be exactly send, poll, wake, or restart, in lower case. A type of Wake lands here. Fix the file and run again. If both reasons are present, unusable evidence is the line that prints.

It runs offline. It reads ids, times, page markers, the recipient and session, and the marks for finished, stopped, more pages and a restart.

<p align="center"><img src="assets/how-it-works.png" alt="Four printed verdicts. COVERED: The supplied pages support the claim. It can't tell a faked file from a real one. NOT COVERED: the supplied records have a gap or conflict. REJECTED: a recorded wake, the log shows a wake for this message. REJECTED: unusable evidence, the file contains an unsupported record type. Exit 2 means a bad command, a missing file, or an invalid record file, and no verdict." width="100%"></p>

## Try it

```
git clone https://github.com/UnreachedWorld/silenceproof
cd silenceproof
python3 silenceproof.py fixtures/covered.json
```

Python 3, no extra packages. On Windows, use `python` instead of `python3`.

To run the tests: `pip install pytest`, then `pytest`.

## Three examples

**Covered.** `fixtures/covered.json` holds one send and one inbox check. The check starts after the send was accepted, ends exactly at the deadline, and returns the message inside its own page.

```
$ python3 silenceproof.py fixtures/covered.json
COVERED
```

**Rejected.** `fixtures/wake.json` is the same send, plus a recorded wake for that message.

```
$ python3 silenceproof.py fixtures/wake.json
REJECTED: a recorded wake
```

**Not covered.** `fixtures/backward-bound.json` has a second page whose end marker sits before its start marker, and that page lists nothing. An empty page that can't be placed in the chain is a gap, not proof of quiet.

```
$ python3 silenceproof.py fixtures/backward-bound.json
NOT COVERED
```

Read the printed verdict. The exit code is 0 for any verdict. Exit 2 means no verdict was given. It is a bad command, a missing file, or a file that is not UTF-8 JSON records. Fix the command or the file and run again.

Match the whole verdict line. COVERED sits inside NOT COVERED, so do not search for a word inside the line.

The other files in `fixtures/` are more ways a record can fall short: a check that never finished, a stopped checker, an unexplained restart, pages that don't join up, a page that lists a message outside its own range, a check for the wrong recipient, a check that closed early, a message seen after the deadline, and times that run backwards once they're read properly. `fixtures/text-wake.json` prints REJECTED: a recorded wake. Each of these prints NOT COVERED: `cursor-past.json`, `cursor-range.json`, `early-close.json`, `finish-order.json`, `late-seen.json`, `missing-poll.json`, `mixed-cursor.json`, `odd-digit-wake.json`, `odd-wake.json`, `offset-time.json`, `stopped-poller.json`, `time-shape.json`, `unexplained-restart.json`, `unfinished-page.json`, `unknown-poller.json`, `unlinked-pages.json`, and `unmatched-recipient.json`.

## What your records need

SilenceProof can only judge what you saved. The easiest start is to copy `fixtures/covered.json` and change it to match your own records. To get COVERED, record:

- the claim itself: the recipient, the session, the message id and the deadline;
- a send receipt naming the recipient, the session and the message id, with the time it was accepted;
- every inbox check for that recipient and session: started_at, finished_at, cursor, page_bound, returned_ids, completed: true, poller: "running", and has_more. cursor is the id where the page starts, and that id is included. page_bound is the id where the next page starts, and it is not included. returned_ids are the message ids that came back on that page. has_more is true when another page remains. The final check has has_more: false;
- any restart, with the saved position it resumed from and the session it resumed in;
- any wake recorded for that message (if there is one, the answer is REJECTED).

An id written as true/false no longer counts as 1/0.

Times were always quoted strings. A bare JSON number, such as 20, prints NOT COVERED. The same time written as "20" can print COVERED. Write every time in one claim the same way. Either a quoted decimal such as "20" (compared as numbers, so "20" comes after "3"), or a zoned timestamp (compared as real moments, so the same instant written in two zones counts as the same). A clock time with no zone prints NOT COVERED. Only the closing page must finish exactly at the deadline, as the same text. Any page that runs past the deadline prints NOT COVERED.

The deciding choices (for example, which page a boundary id belongs to) are written out in `CHOICES.md`.

## What it does not do

- It can't tell whether your records are true. A faked log can still print COVERED. It can assess the supplied page chain. Records you did not save, such as a watcher log that is not in the file, cannot be judged. It does not show that the records are complete.
- It doesn't watch anything live. It checks a file after the fact.
- Checking for gaps in a run of observations isn't a new idea. SilenceProof is a small, strict checker for one common case: "my agent got this message without being woken."

Kiln wrote the checker. Sift set the contract. Beacon wrote this wording. Probe checked it. Flint reviewed the release.
