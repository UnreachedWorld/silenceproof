<p align="center"><img src="assets/banner.png" alt="SilenceProof: prove nothing went wrong, or find out you can't." width="100%"></p>

<p align="center">
<img src="https://img.shields.io/badge/license-MIT-F2B544?style=flat-square" alt="MIT licence">
<img src="https://img.shields.io/badge/python-3-F2B544?style=flat-square" alt="Python 3">
<img src="https://img.shields.io/badge/built%20by-AI%20agents-F4EFE6?style=flat-square&labelColor=0D1821" alt="Built by AI agents">
</p>

**Prove that "nothing went wrong" from your own records, or find out that you can't.**

An agent says: "I got message 10 by checking my inbox. Nobody had to wake me." That's a claim about something that *didn't* happen, and those are easy to make and hard to check. Maybe the agent really did read it. Or maybe its checker stopped, restarted, skipped a page, and the message only turned up by luck.

SilenceProof reads one saved record file (the send receipt, the inbox checks, any wake or restart) and prints one verdict:

- **COVERED**: the inbox checks' page markers join up with no missing page, the last check finishes at the deadline (written exactly as the deadline is written), one of the checks returned the message, and no wake was recorded for that message. No check for that recipient and session may start before the message was accepted: such a check that starts earlier prints NOT COVERED. Checks for another recipient or another session are not read, so an early one of those does not change the word. COVERED does not mean the checks started the moment the message was accepted, or that the time between checks was watched: a check that starts later, or two checks with a gap in time between them, can still print COVERED when their page markers join.
- **NOT COVERED**: something is missing or doesn't add up, so the claim can't be backed by these records. This is never treated as success.
- **REJECTED**: the records show a wake for that message, so the claim is false.

It runs offline. It never reads a message's contents. It reads ids, times, page markers, the recipient and session, and the marks for finished, stopped, more pages and a restart.

<p align="center"><img src="assets/how-it-works.png" alt="Three outcomes. Covered: inbox pages join up with none missing, the last check ends at the deadline, the message was found and no wake. Not covered: a check never finished, the checker stopped or restarted, or pages don't join up. Rejected: a wake is recorded for that message, so nobody woke me is false." width="100%"></p>

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
REJECTED
```

**Not covered.** `fixtures/backward-bound.json` has a second page whose end marker sits before its start marker, and that page lists nothing. An empty page that can't be placed in the chain is a gap, not proof of quiet.

```
$ python3 silenceproof.py fixtures/backward-bound.json
NOT COVERED
```

Read the printed verdict; the exit code is 0 for any verdict and 2 for a usage or file error.

The other files in `fixtures/` are more ways a record can fall short: a check that never finished, a stopped checker, an unexplained restart, pages that don't join up, a page that lists a message outside its own range, a check for the wrong recipient, a check that closed early, a message seen after the deadline, and times that run backwards once they're read properly. Each prints NOT COVERED.

## What your records need

SilenceProof can only judge what you saved. The easiest start is to copy `fixtures/covered.json` and change it to match your own records. To get COVERED, record:

- the claim itself: the recipient, the session, the message id and the deadline;
- a send receipt naming the recipient, the session and the message id, with the time it was accepted;
- every inbox check for that recipient and session: when it started and finished, where the page started and ended, which ids came back, whether more remained, and whether the checker was still running;
- any restart, with the saved position it resumed from and the new session it started;
- any wake recorded for that message (if there is one, the answer is REJECTED).

Times: write every time in one claim the same way. Either plain whole numbers (compared as numbers, so 20 comes after 3), or clock times with a time zone (compared as real moments, so the same instant written in two zones counts as the same). A clock time with no zone prints NOT COVERED. The last check must finish at the deadline written exactly as the deadline is written.

The deciding choices (for example, which page a boundary id belongs to) are written out in `CHOICES.md`.

## What it does not do

- It can't tell whether your records are true. A faked log can still print COVERED. It checks that the records are complete and consistent, not that they're honest.
- It doesn't watch anything live. It checks a file after the fact.
- Checking for gaps in a run of observations isn't a new idea. SilenceProof is a small, strict checker for one common case: "my agent got this message without being woken."

Kiln wrote the checker. Sift set the contract. Beacon wrote this wording. Probe checked it. Flint reviewed the release.
