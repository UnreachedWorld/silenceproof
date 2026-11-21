# What this file does: it reads saved send, poll, wake and restart records and says
# whether a claim that nothing happened is covered.
# The first line is the whole verdict. A second line names the check for NOT COVERED or REJECTED.
# A bool is not a whole-number id. Any other record type is REJECTED.
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
    verdict, _reason = decide(data)
    return verdict


def decide(data):
    """Return the verdict and the one check line. COVERED has no check line."""
    claim = data.get("claim") or {}
    records = data.get("records") or []
    if _unknown_type(records):
        return "REJECTED", "rejected: a record type is not send, poll, wake, or restart"
    recipient = claim.get("recipient")
    session = claim.get("session")
    target = claim.get("target")
    deadline = claim.get("deadline")
    if recipient is None or session is None or target is None or deadline is None:
        return "NOT COVERED", "gap: the claim is missing a recipient, session, message or deadline"
    if _woke(records, recipient, session, target):
        return "REJECTED", "wake: message %s has a recorded wake" % target
    reason = _wake_gap(records, recipient, session)
    if reason:
        return "NOT COVERED", reason
    sends = _sends(records, recipient, session, target)
    if len(sends) == 0:
        return "NOT COVERED", "gap: no send receipt for this message"
    if len(sends) > 1:
        return "NOT COVERED", "gap: more than one send receipt for this message"
    send = sends[0]
    polls = _polls(records, recipient, session)
    if not polls:
        return "NOT COVERED", "gap: no inbox check for this recipient and session"
    reason = _poll_gap(polls, send.get("acknowledged_at"))
    if reason:
        return "NOT COVERED", reason
    reason = _range_gap(polls)
    if reason:
        return "NOT COVERED", reason
    reason = _cursor_already_past(polls, target)
    if reason:
        return "NOT COVERED", reason
    reason = _restart_gap(records)
    if reason:
        return "NOT COVERED", reason
    reason = _time_gap(polls, send.get("acknowledged_at"), deadline)
    if reason:
        return "NOT COVERED", reason
    reason = _chain_gap(polls)
    if reason:
        return "NOT COVERED", reason
    reason = _horizon_gap(polls, deadline)
    if reason:
        return "NOT COVERED", reason
    if not _drained(polls, deadline, target):
        return "NOT COVERED", "gap: no page lists this message"
    return "COVERED", None


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
        return "gap: a wake id is not a whole number"
    return None


def _send_id(found, target):
    """True when both ids are ints and equal. A bool is not an id."""
    if type(found) is not int or type(target) is not int:
        return False
    return found == target


def _unknown_type(records):
    """A record type other than send, poll, wake, or restart rejects the claim."""
    known = ("send", "poll", "wake", "restart")
    for record in records:
        if type(record) is not dict:
            continue
        if record.get("type") not in known:
            return True
    return False


def _sends(records, recipient, session, target):
    """Every send receipt for this target. None and several are different gaps."""
    return [record for record in records if record.get("type") == "send" and _same(record, recipient, session) and _send_id(record.get("id"), target)]


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


def _one_line(value):
    """Show one saved time on a single reason line. The file is unchanged."""
    text = value if type(value) is str else "%s" % (value,)
    shown = []
    for char in text:
        code = ord(char)
        if char == "\\":
            shown.append("\\\\")
        elif char == "\n":
            shown.append("\\n")
        elif char == "\r":
            shown.append("\\r")
        elif char == "\t":
            shown.append("\\t")
        elif not char.isprintable() and code <= 0xFFFF:
            shown.append("\\u%04x" % code)
        elif not char.isprintable():
            shown.append("\\U%08x" % code)
        else:
            shown.append(char)
    return "".join(shown)


def _when(value):
    """Sort key for one time. A refused time sorts last."""
    found = _instant(value)
    if found is None:
        return (2, 0)
    return found


def _same_instant(left, right):
    """True when both times are one instant, even if the spelling differs."""
    first = _instant(left)
    second = _instant(right)
    if first is None or second is None:
        return False
    return first == second


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
            return "gap: a time is not a quoted number or a zoned timestamp"
        kinds.append(found[0])
    if len(set(kinds)) > 1:
        return "gap: times in this claim are not the same kind"
    return None


def _poll_gap(polls, acknowledged_at):
    """A poll that is unfinished, not running, early, or missing its fields is a gap."""
    if acknowledged_at is None:
        return "gap: the send has no accepted time"
    for poll in polls:
        if not _fields(poll):
            return "gap: an inbox check is missing a page field"
        if _earlier(poll.get("started_at"), acknowledged_at):
            return "gap: an inbox check starts before the message was accepted"
        if poll.get("poller") != "running":
            return "gap: an inbox check was not running"
        if poll.get("completed") is not True:
            return "gap: an inbox check did not finish"
    return None


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
    """A listed id must be a whole number on a whole-number page before a range is named."""
    for poll in polls:
        for item in poll.get("returned_ids") or []:
            if type(item) is not int:
                return "gap: a listed id is not a whole number"
            if type(poll.get("cursor")) is not int:
                return "gap: a page cursor is not a whole number"
            if type(poll.get("page_bound")) is not int:
                return "gap: a page bound is not a whole number"
            if not _page_holds(poll, item):
                return "gap: message %s is listed outside page %s-%s" % (item, poll.get("cursor"), poll.get("page_bound"))
    return None


def _cursor_already_past(polls, target):
    """A cursor already past the target, which never sits inside a page, is a gap."""
    if type(target) is not int:
        return None
    seen = any(_page_holds(poll, target) and target in poll.get("returned_ids", []) for poll in polls)
    if seen:
        return None
    for poll in polls:
        if type(poll.get("cursor")) is int and poll.get("cursor") > target:
            return "gap: a page starts at %s, after message %s, and no page lists it" % (poll.get("cursor"), target)
    return None


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
        if type(cursor) is not int:
            return "gap: a restart has no whole-number saved position"
        if type(session) is not str or session == "":
            return "gap: a restart has no session"
        previous = _adjacent_poll(records, index, -1)
        following = _adjacent_poll(records, index, 1)
        if previous is None or following is None:
            return "gap: a restart has no inbox check on either side"
        if previous.get("page_bound") != cursor or following.get("cursor") != cursor:
            return "gap: a restart at %s does not continue the pages on either side" % cursor
        if following.get("session") != session:
            return "gap: a restart resumes in a different session"
    return None


def _pages_join(ordered):
    """True when each page starts where the previous page ends."""
    previous = None
    for poll in ordered:
        if previous is not None and poll.get("cursor") != previous.get("page_bound"):
            return False
        previous = poll
    return True


def _time_order_line(ordered):
    """The first id-order pair whose later page started earlier, or nothing."""
    previous = None
    for poll in ordered:
        if previous is not None and _earlier(poll.get("started_at"), previous.get("started_at")):
            return "gap: page %s-%s starts after page %s-%s in time, so the pages are out of order" % (previous.get("cursor"), previous.get("page_bound"), poll.get("cursor"), poll.get("page_bound"))
        previous = poll
    return None


def _chain_walk(ordered):
    """One page order must join, and a later page must not close before the page it continues."""
    previous = None
    terminals = 0
    for poll in ordered:
        if poll.get("page_bound") < poll.get("cursor"):
            return "gap: page %s-%s ends before it starts" % (poll.get("cursor"), poll.get("page_bound"))
        if _earlier(poll.get("finished_at"), poll.get("started_at")):
            return "gap: page %s-%s finishes before it starts" % (poll.get("cursor"), poll.get("page_bound"))
        if previous is not None and poll.get("cursor") != previous.get("page_bound"):
            return "gap: pages %s-%s and %s-%s do not join" % (previous.get("cursor"), previous.get("page_bound"), poll.get("cursor"), poll.get("page_bound"))
        if previous is not None and _earlier(poll.get("finished_at"), previous.get("finished_at")):
            return "gap: page %s-%s finishes before page %s-%s" % (poll.get("cursor"), poll.get("page_bound"), previous.get("cursor"), previous.get("page_bound"))
        if poll.get("has_more") is False:
            terminals = terminals + 1
        elif poll.get("has_more") is not True:
            return "gap: a page does not say whether more pages remain"
        previous = poll
    if terminals != 1 or ordered[-1].get("has_more") is not False:
        return "gap: the pages do not end on one last page"
    return None


def _chain_gap(polls):
    """Pages are checked in time order. A broken join that still joins by id names the time order."""
    for poll in polls:
        if type(poll.get("cursor")) is not int:
            return "gap: a page cursor is not a whole number"
        if type(poll.get("page_bound")) is not int:
            return "gap: a page bound is not a whole number"
    by_time = sorted(polls, key=lambda poll: (_when(poll.get("started_at")), poll.get("cursor")))
    found = _chain_walk(by_time)
    if found is None:
        return None
    if found.startswith("gap: pages ") and found.endswith(" do not join"):
        by_id = sorted(polls, key=lambda poll: poll.get("cursor"))
        if _pages_join(by_id):
            named = _time_order_line(by_id)
            if named is not None:
                return named
    return found


def _horizon_gap(polls, deadline):
    """A page past the deadline, or a close before the deadline, is a gap."""
    for poll in polls:
        if _earlier(deadline, poll.get("started_at")) or _earlier(deadline, poll.get("finished_at")):
            return "gap: page %s-%s runs past the deadline" % (poll.get("cursor"), poll.get("page_bound"))
    closing = [poll for poll in polls if poll.get("has_more") is False]
    if len(closing) != 1:
        return "gap: the pages do not end on one last page"
    finished = closing[0].get("finished_at")
    if finished != deadline:
        if _same_instant(finished, deadline):
            return "gap: the closing time is the same instant but not the same text"
        return "gap: the closing page finishes at %s, not the deadline" % _one_line(finished)
    return None


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


def _reject_line(data):
    """Name which REJECTED reason this claim hit. Unusable evidence is not a wake."""
    records = data.get("records") or []
    if _unknown_type(records):
        return "REJECTED: unusable evidence"
    return "REJECTED: a recorded wake"


def main(argv):
    """Print the verdict and the deciding check, or one plain error for a bad command, a missing file, or a file that is not UTF-8 JSON records."""
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
    word, reason = decide(data)
    if word == "REJECTED":
        print(_reject_line(data))
    else:
        print(word)
    if reason:
        print(reason)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
