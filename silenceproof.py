# What this file does: it reads saved send, poll and wake records and says
# whether a claim that nothing happened is covered.
# Kiln wrote the checker. Sift set the contract. Beacon wrote the public wording.
# It does not use the network, and it does not read a message body.

import json
import sys
from datetime import datetime
from pathlib import Path


def load(path):
    """Read one record file."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def check(data):
    """Return COVERED, NOT COVERED, or REJECTED for one negative claim."""
    claim = data.get("claim") or {}
    records = data.get("records") or []
    recipient = claim.get("recipient")
    session = claim.get("session")
    target = claim.get("target")
    deadline = claim.get("deadline")
    if recipient is None or session is None or target is None or deadline is None:
        return "NOT COVERED"
    if _woke(records, recipient, session, target):
        return "REJECTED"
    if _wake_gap(records, recipient, session):
        return "NOT COVERED"
    send = _send(records, recipient, session, target)
    if send is None:
        return "NOT COVERED"
    polls = _polls(records, recipient, session)
    if not polls:
        return "NOT COVERED"
    if _poll_gap(polls, send.get("acknowledged_at")):
        return "NOT COVERED"
    if _range_gap(polls):
        return "NOT COVERED"
    if _cursor_already_past(polls, target):
        return "NOT COVERED"
    if _restart_gap(records):
        return "NOT COVERED"
    if _time_gap(polls, send.get("acknowledged_at"), deadline):
        return "NOT COVERED"
    if _chain_gap(polls):
        return "NOT COVERED"
    if _horizon_gap(polls, deadline):
        return "NOT COVERED"
    if not _drained(polls, deadline, target):
        return "NOT COVERED"
    return "COVERED"


def _whole_text(text):
    """The whole number in this ASCII decimal, or None when the text is not one."""
    if type(text) is not str or not text.isascii() or not text.isdigit():
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _same_id(found, target):
    """True when a wake id is the same whole number as the target, including decimal text."""
    if type(target) is not int or type(found) is bool:
        return False
    if type(found) is int:
        return found == target
    number = _whole_text(found)
    if number is None:
        return False
    return number == target


def _woke(records, recipient, session, target):
    """A wake record for this target rejects the claim that nothing happened."""
    return any(_same(record, recipient, session) and _same_id(record.get("id"), target) for record in records if type(record) is dict and record.get("type") == "wake")


def _wake_gap(records, recipient, session):
    """A wake for this claim whose id is not a whole number cannot be checked."""
    for record in records:
        if type(record) is not dict or record.get("type") != "wake" or not _same(record, recipient, session):
            continue
        found = record.get("id")
        if type(found) is int or _whole_text(found) is not None:
            continue
        return True
    return False


def _send(records, recipient, session, target):
    """Return the one send receipt for this target, or nothing."""
    found = [record for record in records if record.get("type") == "send" and _same(record, recipient, session) and record.get("id") == target]
    if len(found) != 1:
        return None
    return found[0]


def _polls(records, recipient, session):
    """Return polls that name this recipient and session."""
    return [record for record in records if record.get("type") == "poll" and _same(record, recipient, session)]


def _same(record, recipient, session):
    """A record matches the claim's recipient and session."""
    return record.get("recipient") == recipient and record.get("session") == session


def _instant(value):
    """A whole number stays a number. A zoned clock time becomes one instant. Anything else is refused."""
    if type(value) is not str or value == "":
        return None
    number = _whole_text(value)
    if number is not None:
        return ("n", number)
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return ("t", parsed.timestamp())


def _when(value):
    """Sort key for one time. A refused time sorts last."""
    found = _instant(value)
    if found is None:
        return (2, 0)
    return found


def _earlier(left, right):
    """True when left is before right as a number or as a real instant."""
    first = _instant(left)
    second = _instant(right)
    if first is None or second is None:
        return False
    return first < second


def _time_gap(polls, acknowledged_at, deadline):
    """Every time in one claim must be the same kind, so text order cannot hide a backward chain."""
    values = [acknowledged_at, deadline]
    for poll in polls:
        values.append(poll.get("started_at"))
        values.append(poll.get("finished_at"))
    kinds = []
    for value in values:
        found = _instant(value)
        if found is None:
            return True
        kinds.append(found[0])
    if len(set(kinds)) > 1:
        return True
    return False


def _poll_gap(polls, acknowledged_at):
    """A poll that is unfinished, not running, early, or missing its fields is a gap."""
    if acknowledged_at is None:
        return True
    for poll in polls:
        if not _fields(poll):
            return True
        if _earlier(poll.get("started_at"), acknowledged_at):
            return True
        if poll.get("poller") != "running":
            return True
        if poll.get("completed") is not True:
            return True
    return False


def _fields(poll):
    """A poll must carry the fields the contract says a producer records."""
    needed = ("cursor", "page_bound", "returned_ids", "has_more", "started_at", "finished_at", "completed", "poller")
    return all(key in poll for key in needed)


def _page_holds(poll, item):
    """An id belongs to a page from its cursor up to, and not including, its page bound."""
    cursor = poll.get("cursor")
    bound = poll.get("page_bound")
    if type(cursor) is not int or type(bound) is not int or type(item) is not int:
        return False
    if item < cursor or item >= bound:
        return False
    return True


def _range_gap(polls):
    """A returned id outside its own page is contradictory."""
    for poll in polls:
        for item in poll.get("returned_ids") or []:
            if not _page_holds(poll, item):
                return True
    return False


def _cursor_already_past(polls, target):
    """A cursor already past the target, which never sits inside a page, is a gap."""
    if type(target) is not int:
        return False
    seen = any(_page_holds(poll, target) and target in poll.get("returned_ids", []) for poll in polls)
    if seen:
        return False
    return any(type(poll.get("cursor")) is int and poll.get("cursor") > target for poll in polls)


def _adjacent_poll(records, index, step):
    """The next poll record in that direction, skipping anything that is not a poll."""
    point = index + step
    while 0 <= point < len(records):
        record = records[point]
        if type(record) is dict and record.get("type") == "poll":
            return record
        point = point + step
    return None


def _restart_gap(records):
    """A restart that does not continue the poll on either side is unexplained."""
    for index, record in enumerate(records):
        if type(record) is not dict or record.get("type") != "restart":
            continue
        cursor = record.get("persisted_cursor")
        session = record.get("session_boundary")
        if type(cursor) is not int or type(session) is not str or session == "":
            return True
        previous = _adjacent_poll(records, index, -1)
        following = _adjacent_poll(records, index, 1)
        if previous is None or following is None:
            return True
        if previous.get("page_bound") != cursor or following.get("cursor") != cursor:
            return True
        if following.get("session") != session:
            return True
    return False


def _chain_gap(polls):
    """Whole-number pages must join, and a later page must not close before the page it continues."""
    for poll in polls:
        if type(poll.get("cursor")) is not int or type(poll.get("page_bound")) is not int:
            return True
    ordered = sorted(polls, key=lambda poll: (_when(poll.get("started_at")), poll.get("cursor")))
    previous = None
    terminals = 0
    for poll in ordered:
        if poll.get("page_bound") < poll.get("cursor"):
            return True
        if _earlier(poll.get("finished_at"), poll.get("started_at")):
            return True
        if previous is not None and poll.get("cursor") != previous.get("page_bound"):
            return True
        if previous is not None and _earlier(poll.get("finished_at"), previous.get("finished_at")):
            return True
        if poll.get("has_more") is False:
            terminals = terminals + 1
        elif poll.get("has_more") is not True:
            return True
        previous = poll
    if terminals != 1:
        return True
    if ordered[-1].get("has_more") is not False:
        return True
    return False


def _horizon_gap(polls, deadline):
    """A page past the deadline, or a close before the deadline, is a gap."""
    for poll in polls:
        if _earlier(deadline, poll.get("started_at")) or _earlier(deadline, poll.get("finished_at")):
            return True
    closing = [poll for poll in polls if poll.get("has_more") is False]
    if len(closing) != 1:
        return True
    if closing[0].get("finished_at") != deadline:
        return True
    return False


def _drained(polls, deadline, target):
    """The chain ends on the deadline, and a page inside the deadline saw the target."""
    finished = [poll for poll in polls if poll.get("has_more") is False and poll.get("finished_at") == deadline]
    seen = any(_page_holds(poll, target) and target in poll.get("returned_ids", []) and not _earlier(deadline, poll.get("finished_at")) for poll in polls)
    return bool(finished) and seen


def _record_shape(data):
    """True when the claim and every record are objects, and page ids are a list."""
    if type(data) is not dict:
        return False
    claim = data.get("claim", {})
    records = data.get("records", [])
    if type(claim) is not dict or type(records) is not list:
        return False
    for record in records:
        if type(record) is not dict:
            return False
        if "returned_ids" in record and type(record.get("returned_ids")) is not list:
            return False
    return True


def main(argv):
    """Print one verdict, or one plain error line for a bad command or file."""
    if len(argv) != 2 or argv[1] == "--help" or argv[1].startswith("-"):
        print("usage: python3 silenceproof.py FILE", file=sys.stderr)
        return 2
    if not Path(argv[1]).is_file():
        print("No such file.", file=sys.stderr)
        return 2
    try:
        data = load(argv[1])
    except (json.JSONDecodeError, UnicodeDecodeError):
        print("not a JSON record file", file=sys.stderr)
        return 2
    if not _record_shape(data):
        print("not a JSON record file", file=sys.stderr)
        return 2
    print(check(data))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
