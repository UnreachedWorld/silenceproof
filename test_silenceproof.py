# What this file does: it checks SilenceProof on fictional records.
# Nothing here uses the network.

import copy
import json
import random
from pathlib import Path

import silenceproof


ROOT = Path(__file__).resolve().parent
FIXTURES = ROOT / "fixtures"


def load(name):
    """Read one fictional fixture."""
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_a_covered_negative_is_accepted():
    """A poll that finishes on the deadline and saw the target is COVERED."""
    assert silenceproof.check(load("covered.json")) == "COVERED"


def test_a_text_wake_id_for_the_target_is_rejected():
    """A wake id written as the decimal of the target is still a wake."""
    assert silenceproof.check(load("text-wake.json")) == "REJECTED"


def test_json_true_is_not_a_send_id():
    """JSON true is not the whole number 1, so the send does not match."""
    data = load("covered.json")
    data["claim"]["target"] = 1
    data["records"][0]["id"] = True
    data["records"][1]["returned_ids"] = [1]
    assert silenceproof.check(data) == "NOT COVERED"


def test_an_unknown_or_near_miss_type_is_rejected():
    """A record type other than the known words rejects the claim."""
    for mark in ("Wake", "wake ", "note"):
        data = load("covered.json")
        data["records"].append({
            "type": mark,
            "recipient": "room-a",
            "session": "s1",
            "id": 10,
        })
        assert silenceproof.check(data) == "REJECTED", mark


def test_a_strange_digit_is_not_covered_and_does_not_crash(capsys):
    """A digit that int() refuses prints NOT COVERED and no traceback."""
    assert silenceproof.check(load("odd-digit-wake.json")) == "NOT COVERED"
    code = silenceproof.main(["silenceproof", str(FIXTURES / "odd-digit-wake.json")])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == "NOT COVERED\ngap: a wake id is not a whole number\n"
    assert captured.err == ""
    assert "Traceback" not in captured.out


def test_a_strange_digit_time_is_not_covered():
    """A clock field that is only a strange digit is a gap, not a crash."""
    data = load("covered.json")
    data["records"][1]["started_at"] = "²"
    assert silenceproof.check(data) == "NOT COVERED"


def test_a_wake_id_that_is_not_a_whole_number_is_not_covered():
    """A wake id that cannot be compared with the target is a gap, not silence."""
    assert silenceproof.check(load("odd-wake.json")) == "NOT COVERED"


def test_a_wake_is_rejected():
    """A recorded wake is not called silence and not called a gap."""
    word = silenceproof.check(load("wake.json"))
    assert word == "REJECTED"
    assert word not in ("COVERED", "NOT COVERED", "success", "PASS")


def test_each_gap_is_not_covered():
    """Each named gap answers NOT COVERED."""
    for name in (
        "cursor-past.json",
        "unfinished-page.json",
        "missing-poll.json",
        "stopped-poller.json",
        "unexplained-restart.json",
        "unmatched-recipient.json",
        "early-close.json",
        "late-seen.json",
        "unlinked-pages.json",
        "cursor-range.json",
        "backward-bound.json",
        "time-shape.json",
        "offset-time.json",
    ):
        assert silenceproof.check(load(name)) == "NOT COVERED", name


def test_the_command_prints_one_word(capsys):
    """The command prints the covered fixture's word and nothing else."""
    code = silenceproof.main(["silenceproof", str(FIXTURES / "covered.json")])
    assert code == 0
    assert capsys.readouterr().out == "COVERED\n"


def test_a_missing_file_prints_a_plain_error(capsys, tmp_path):
    """A missing file prints one plain line and no traceback."""
    missing = tmp_path / "no-such.json"
    code = silenceproof.main(["silenceproof", str(missing)])
    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert captured.err == "No such file.\n"
    assert "Traceback" not in captured.err


USAGE = "usage: python3 silenceproof.py FILE\n"


def test_no_file_prints_usage_and_exits_2(capsys):
    """No file is a usage error, not a verdict."""
    code = silenceproof.main(["silenceproof"])
    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert captured.err == USAGE
    assert "NOT COVERED" not in captured.err
    assert "Traceback" not in captured.err


def test_extra_arguments_print_usage_and_exit_2(capsys):
    """An extra argument is a usage error, not a verdict."""
    code = silenceproof.main(["silenceproof", "one.json", "two.json"])
    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert captured.err == USAGE


def test_help_prints_usage_and_exits_2(capsys):
    """--help is the same usage line, including when it is the only argument."""
    code = silenceproof.main(["silenceproof", "--help"])
    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert captured.err == USAGE


def test_malformed_json_prints_one_plain_line(capsys, tmp_path):
    """A file that is not JSON prints one plain line and does not traceback."""
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    code = silenceproof.main(["silenceproof", str(bad)])
    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert captured.err == "not a JSON record file\n"
    assert "Traceback" not in captured.err


def test_a_file_that_is_not_utf8_prints_one_plain_line(capsys, tmp_path):
    """Bytes that are not UTF-8 text get the same plain line and exit 2."""
    bad = tmp_path / "bad.json"
    bad.write_bytes(b"\xff")
    code = silenceproof.main(["silenceproof", str(bad)])
    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert captured.err == "not a JSON record file\n"
    assert "Traceback" not in captured.err


def test_a_json_value_that_is_not_a_record_is_refused(capsys, tmp_path):
    """A JSON list is not a record file, so it gets the same plain line."""
    bad = tmp_path / "list.json"
    bad.write_text("[]", encoding="utf-8")
    code = silenceproof.main(["silenceproof", str(bad)])
    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert captured.err == "not a JSON record file\n"
    assert "Traceback" not in captured.err


def test_a_wake_and_unusable_evidence_print_different_reasons(capsys, tmp_path):
    """A recorded wake and a bad record type are two REJECTED reasons."""
    code = silenceproof.main(["silenceproof", str(FIXTURES / "wake.json")])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == "REJECTED: a recorded wake\nwake: message 10 has a recorded wake\n"
    data = load("covered.json")
    data["records"].append({"type": "Wake", "recipient": "room-a", "session": "s1", "id": 10})
    path = tmp_path / "near.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    code = silenceproof.main(["silenceproof", str(path)])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == (
        "REJECTED: unusable evidence\n"
        "rejected: a record type is not send, poll, wake, or restart\n"
    )
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "a recorded wake" in readme
    assert "unusable evidence" in readme


def test_each_verdict_exits_zero(capsys):
    """COVERED, REJECTED and NOT COVERED each print the verdict and exit 0."""
    expected = (
        ("covered.json", "COVERED\n"),
        ("wake.json", "REJECTED: a recorded wake\nwake: message 10 has a recorded wake\n"),
        ("backward-bound.json", "NOT COVERED\ngap: page 20-5 ends before it starts\n"),
    )
    for name, word in expected:
        code = silenceproof.main(["silenceproof", str(FIXTURES / name)])
        captured = capsys.readouterr()
        assert code == 0
        assert captured.out == word
        assert captured.err == ""


def _continued():
    """A covered chain with a restart that resumes at the next page in the same session."""
    data = load("covered.json")
    data["records"] = [
        data["records"][0],
        {
            "type": "poll",
            "recipient": "room-a",
            "session": "s1",
            "started_at": "2026-11-07T10:05:00Z",
            "finished_at": "2026-11-07T11:00:00Z",
            "cursor": 1,
            "page_bound": 10,
            "returned_ids": [],
            "has_more": True,
            "completed": True,
            "poller": "running",
        },
        {
            "type": "restart",
            "persisted_cursor": 10,
            "session_boundary": "s1",
        },
        {
            "type": "poll",
            "recipient": "room-a",
            "session": "s1",
            "started_at": "2026-11-07T11:05:00Z",
            "finished_at": "2026-11-07T12:00:00Z",
            "cursor": 10,
            "page_bound": 20,
            "returned_ids": [10],
            "has_more": False,
            "completed": True,
            "poller": "running",
        },
    ]
    return data


def test_a_restart_that_continues_the_polls_is_covered():
    """A typed cursor and session that match the polls on either side stay COVERED."""
    assert silenceproof.check(_continued()) == "COVERED"


def test_a_restart_that_does_not_continue_the_polls_is_not_covered():
    """A saved cursor or session that does not match the surrounding polls is a gap."""
    wrong_cursor = _continued()
    wrong_cursor["records"][2]["persisted_cursor"] = 99
    wrong_session = _continued()
    wrong_session["records"][2]["session_boundary"] = "s2"
    text_cursor = _continued()
    text_cursor["records"][2]["persisted_cursor"] = "10"
    flag_session = _continued()
    flag_session["records"][2]["session_boundary"] = True
    no_next = _continued()
    restart = no_next["records"].pop(2)
    no_next["records"].append(restart)
    for data in (wrong_cursor, wrong_session, text_cursor, flag_session, no_next):
        assert silenceproof.check(data) == "NOT COVERED"


def test_a_bad_nested_shape_prints_the_plain_line(capsys, tmp_path):
    """A record that is not an object prints one plain line and does not traceback."""
    bad = tmp_path / "shape.json"
    body = (
        '{"claim": {"recipient": "room-a", "session": "s1", "target": 10, '
        '"deadline": "2026-11-07T12:00:00Z"}, "records": [1]}\n'
    )
    bad.write_text(body, encoding="utf-8")
    code = silenceproof.main(["silenceproof", str(bad)])
    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert captured.err == "not a JSON record file\n"
    assert "Traceback" not in captured.err


def test_a_page_id_list_that_is_not_a_list_prints_the_plain_line(capsys, tmp_path):
    """A page whose ids are not a list prints one plain line and does not traceback."""
    data = load("covered.json")
    data["records"][1]["returned_ids"] = 5
    bad = tmp_path / "ids.json"
    bad.write_text(json.dumps(data), encoding="utf-8")
    code = silenceproof.main(["silenceproof", str(bad)])
    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert captured.err == "not a JSON record file\n"
    assert "Traceback" not in captured.err


def test_a_later_page_that_closes_too_early_is_not_covered():
    """A page that finishes before the page it continues is a gap."""
    assert silenceproof.check(load("finish-order.json")) == "NOT COVERED"


def test_an_unknown_poller_is_not_covered():
    """A poller mark other than running is not evidence the checker was still going."""
    assert silenceproof.check(load("unknown-poller.json")) == "NOT COVERED"


def test_mixed_cursor_types_do_not_crash(capsys):
    """Cursors of different types print NOT COVERED and do not traceback."""
    assert silenceproof.check(load("mixed-cursor.json")) == "NOT COVERED"
    code = silenceproof.main(["silenceproof", str(FIXTURES / "mixed-cursor.json")])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == "NOT COVERED\ngap: a page cursor is not a whole number\n"
    assert captured.err == ""
    assert "Traceback" not in captured.out


def test_the_readme_states_the_exit_codes():
    """The README tells a reader to trust the printed verdict, not the exit code."""
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    line = "Read the printed verdict. The exit code is 0 for any verdict. Exit 2 means no verdict was given. It is a bad command, a missing file, or a file that is not UTF-8 JSON records. Fix the command or the file and run again."
    assert text.count(line) == 1


def test_the_readme_names_the_015_lines():
    """The README names the plain verdicts and keeps the record rules."""
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    card = "COVERED: The supplied pages support the claim. It can't tell a faked file from a real one."
    covered = "- **COVERED**: the saved inbox checks found the message, the pages join up to the deadline, and the file records no wake for that message."
    unusable = "Unusable evidence means a record has an unsupported type. This verdict leaves the claim unresolved."
    kept = "COVERED does not mean the checks started the moment the message was accepted, or that the time between checks was watched: a check that starts later, or two checks with a gap in time between them, can still print COVERED when their page markers join."
    assert text.count(card) == 1
    assert text.count("Match the whole verdict line.") == 1
    assert text.count("An id written as true/false no longer counts as 1/0.") == 1
    assert text.count("Times were always quoted strings.") == 1
    assert "Times are always quoted strings." not in text
    assert text.count(covered) == 1
    assert "the matching inbox checks" not in text
    assert text.count(unusable) == 1
    assert "the file has a record the checker cannot read" not in text
    assert text.count(kept) == 1
    assert text.index("## What your records need") < text.index(kept)
    repeated = "The same id listed twice on one page still counts as that message, and can print COVERED."
    assert text.count(repeated) == 1
    second = "A second line names the check that decided NOT COVERED or REJECTED. COVERED stays one line."
    assert text.count(second) == 1
    assert text.count("Scripts should match only the first line.") == 1
    assert text.count("The line does not say which gap it was.") == 0
    assert text.count("The first line does not say which gap it was; a second line names the check.") == 1
    local = "\n".join((
        "git clone https://github.com/UnreachedWorld/proofscope ../proofscope",
        "git -C ../proofscope checkout 4630995155f3976ec89f48099beb8abcb68c5a49",
        "python3 -m pytest test_silenceproof.py --junitxml=build/junit.xml",
        "python3 ../proofscope/proofscope.py --expected expected-tests.txt --results build/junit.xml",
    ))
    assert text.count(local) == 1
    assert "python3 proofscope.py --expected expected-tests.txt --results build/junit.xml" not in text
    assert "python -m pytest" not in text
    reasons = (
        "gap: the claim is missing a recipient, session, message or deadline",
        "gap: a wake id is not a whole number",
        "wake: message 10 has a recorded wake",
        "gap: no send receipt for this message",
        "gap: more than one send receipt for this message",
        "gap: no inbox check for this recipient and session",
        "gap: the send has no accepted time",
        "gap: an inbox check is missing a page field",
        "gap: an inbox check starts before the message was accepted",
        "gap: an inbox check was not running",
        "gap: an inbox check did not finish",
        "gap: a listed id is not a whole number",
        "gap: message 10 is listed outside page 50-60",
        "gap: a page starts at 50, after message 10, and no page lists it",
        "gap: a restart has no whole-number saved position",
        "gap: a restart has no session",
        "gap: a restart has no inbox check on either side",
        "gap: a restart at 10 does not continue the pages on either side",
        "gap: a restart resumes in a different session",
        "gap: a time is not a quoted number or a zoned timestamp",
        "gap: times in this claim are not the same kind",
        "gap: a page cursor is not a whole number",
        "gap: a page bound is not a whole number",
        "gap: page 20-5 ends before it starts",
        "gap: page 1-20 finishes before it starts",
        "gap: pages 1-20 and 999-1000 do not join",
        "gap: page 1-20 starts after page 20-40 in time, so the pages are out of order",
        "gap: page 11-15 finishes before page 1-11",
        "gap: a page does not say whether more pages remain",
        "gap: the pages do not end on one last page",
        "gap: page 1-20 runs past the deadline",
        "gap: the closing page finishes at 2026-11-07T10:06:00Z, not the deadline",
        "gap: the closing time is the same instant but not the same text",
        "gap: no page lists this message",
        "rejected: a record type is not send, poll, wake, or restart",
    )
    shown_twice = {
        "wake: message 10 has a recorded wake",
        "gap: page 20-5 ends before it starts",
    }
    for reason in reasons:
        expect = 2 if reason in shown_twice else 1
        assert text.count(reason) == expect, reason


def test_the_readme_names_the_restart_keys():
    """The README names both restart keys under What your records need."""
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    needed = text.split("## What your records need", 1)[1]
    assert needed.count("persisted_cursor") == 1
    assert needed.count("session_boundary") == 1
    assert "fixtures/explained-restart.json" in needed


def test_an_explained_restart_fixture_prints_covered(capsys):
    """A saved restart that continues the polls prints COVERED."""
    code = silenceproof.main(["silenceproof", str(FIXTURES / "explained-restart.json")])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == "COVERED\n"
    assert captured.err == ""


REASONS = {
    "backward-bound.json": "NOT COVERED\ngap: page 20-5 ends before it starts\n",
    "covered.json": "COVERED\n",
    "cursor-past.json": "NOT COVERED\ngap: a page starts at 50, after message 10, and no page lists it\n",
    "cursor-range.json": "NOT COVERED\ngap: message 10 is listed outside page 50-60\n",
    "early-close.json": "NOT COVERED\ngap: the closing page finishes at 2026-11-07T10:06:00Z, not the deadline\n",
    "explained-restart.json": "COVERED\n",
    "finish-order.json": "NOT COVERED\ngap: page 11-15 finishes before page 1-11\n",
    "late-seen.json": "NOT COVERED\ngap: message 10 is listed outside page 20-40\n",
    "missing-poll.json": "NOT COVERED\ngap: an inbox check did not finish\n",
    "mixed-cursor.json": "NOT COVERED\ngap: a page cursor is not a whole number\n",
    "odd-digit-wake.json": "NOT COVERED\ngap: a wake id is not a whole number\n",
    "odd-wake.json": "NOT COVERED\ngap: a wake id is not a whole number\n",
    "offset-time.json": "NOT COVERED\ngap: page 1-20 starts after page 20-40 in time, so the pages are out of order\n",
    "stopped-poller.json": "NOT COVERED\ngap: an inbox check was not running\n",
    "text-wake.json": "REJECTED: a recorded wake\nwake: message 10 has a recorded wake\n",
    "time-shape.json": "NOT COVERED\ngap: page 1-20 starts after page 20-40 in time, so the pages are out of order\n",
    "unexplained-restart.json": "NOT COVERED\ngap: a restart has no whole-number saved position\n",
    "unfinished-page.json": "NOT COVERED\ngap: the pages do not end on one last page\n",
    "unknown-poller.json": "NOT COVERED\ngap: an inbox check was not running\n",
    "unlinked-pages.json": "NOT COVERED\ngap: pages 1-20 and 999-1000 do not join\n",
    "unmatched-recipient.json": "NOT COVERED\ngap: no inbox check for this recipient and session\n",
    "wake.json": "REJECTED: a recorded wake\nwake: message 10 has a recorded wake\n",
}


def _covered_copy(tmp_path, name, change):
    """One changed copy of the covered fixture."""
    data = load("covered.json")
    change(data)
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_two_send_receipts_name_the_extra_receipt(tmp_path, capsys):
    """Two matching send receipts are not the same as no receipt."""
    def change(data):
        data["records"].insert(0, dict(data["records"][0]))
    path = _covered_copy(tmp_path, "two-sends.json", change)
    code = silenceproof.main(["silenceproof", str(path)])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.err == ""
    assert captured.out == "NOT COVERED\ngap: more than one send receipt for this message\n"
    assert silenceproof.check(json.loads(path.read_text(encoding="utf-8"))) == "NOT COVERED"


def test_a_text_id_on_the_page_is_not_called_outside(tmp_path, capsys):
    """A text id inside the page is not a whole number, so it is not a range gap."""
    def change(data):
        data["records"][1]["returned_ids"] = ["10"]
    path = _covered_copy(tmp_path, "text-id.json", change)
    code = silenceproof.main(["silenceproof", str(path)])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.err == ""
    assert captured.out == "NOT COVERED\ngap: a listed id is not a whole number\n"
    assert silenceproof.check(json.loads(path.read_text(encoding="utf-8"))) == "NOT COVERED"


def test_the_same_instant_with_different_text_names_the_text(tmp_path, capsys):
    """The same instant spelled +00:00 against Z is a text mismatch, not a different time."""
    def change(data):
        data["records"][1]["finished_at"] = "2026-11-07T12:00:00+00:00"
    path = _covered_copy(tmp_path, "deadline-text.json", change)
    code = silenceproof.main(["silenceproof", str(path)])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.err == ""
    assert captured.out == "NOT COVERED\ngap: the closing time is the same instant but not the same text\n"
    assert silenceproof.check(json.loads(path.read_text(encoding="utf-8"))) == "NOT COVERED"


def test_an_earlier_empty_page_after_the_close_stays_covered(tmp_path, capsys):
    """An earlier empty page written after the closing page stays covered."""
    def change(data):
        closing = data["records"][1]
        empty = dict(closing)
        empty["started_at"] = "2026-11-07T10:04:00Z"
        empty["finished_at"] = "2026-11-07T10:04:00Z"
        empty["cursor"] = 1
        empty["page_bound"] = 1
        empty["returned_ids"] = []
        empty["has_more"] = True
        data["records"].append(empty)
    path = _covered_copy(tmp_path, "empty-before.json", change)
    code = silenceproof.main(["silenceproof", str(path)])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.err == ""
    assert captured.out == "COVERED\n"
    assert silenceproof.check(json.loads(path.read_text(encoding="utf-8"))) == "COVERED"


def test_every_fixture_names_the_deciding_check(capsys):
    """Every fixture keeps its verdict on the first line and names the check on the next."""
    names = sorted(path.name for path in FIXTURES.glob("*.json"))
    assert names == sorted(REASONS)
    for name in names:
        code = silenceproof.main(["silenceproof", str(FIXTURES / name)])
        captured = capsys.readouterr()
        assert code == 0
        assert captured.err == ""
        assert captured.out == REASONS[name]
        first = captured.out.splitlines()[0]
        assert first in ("COVERED", "NOT COVERED", "REJECTED: a recorded wake", "REJECTED: unusable evidence")
        if first == "COVERED":
            assert captured.out == "COVERED\n"


SEED = 20261120
CASES = 480


def _wake(data, found):
    """Add one wake for this claim. The target stays listed on the poll."""
    data["records"].append({"type": "wake", "recipient": "room-a", "session": "s1", "id": found})


def _other_room(data):
    """Add one poll for another room. It must not fill a gap in this claim."""
    data["records"].append({
        "type": "poll",
        "recipient": "room-b",
        "session": "s9",
        "started_at": "2026-11-07T10:05:00Z",
        "finished_at": "2026-11-07T12:00:00Z",
        "cursor": 1,
        "page_bound": 20,
        "returned_ids": [10],
        "has_more": False,
        "completed": True,
        "poller": "running",
    })


def _take(data, fresh):
    """Replace this record with a fresh one, keeping the same object."""
    data.clear()
    data.update(fresh)


def _spoil_wake_int(data, rng):
    """A wake whose id is the target as a number."""
    _wake(data, 10)


def _spoil_wake_text(data, rng):
    """A wake whose id is the target written as an ASCII decimal."""
    _wake(data, rng.choice(["10", "010", "0010"]))


def _spoil_wake_odd(data, rng):
    """A wake whose id is not a whole number, so it cannot be checked."""
    found = rng.choice(["later", "²", "10.0", " 10", "+10", "１０", "10 ", True, None])
    _wake(data, found)


def _spoil_early_finish(data, rng):
    """The page lists the target and closes before the deadline."""
    minute = rng.randrange(0, 50)
    data["records"][1]["finished_at"] = f"2026-11-07T11:{minute:02d}:00Z"


def _spoil_late_finish(data, rng):
    """The page lists the target and closes after the deadline."""
    minute = rng.randrange(1, 60)
    data["records"][1]["finished_at"] = f"2026-11-07T12:{minute:02d}:00Z"


def _spoil_same_instant_other_text(data, rng):
    """The same instant written with another zone text, while the target stays listed."""
    which = rng.randrange(3)
    if which == 0:
        data["records"][1]["finished_at"] = "2026-11-07T12:00:00+00:00"
        return
    if which == 1:
        data["records"][1]["finished_at"] = "2026-11-07T13:00:00+01:00"
        return
    data["claim"]["deadline"] = "2026-11-07T12:00:00+00:00"


def _spoil_mixed_kind(data, rng):
    """One time is a number and the others are clocks, so the chain can hide order."""
    number = str(rng.randrange(0, 5000))
    which = rng.randrange(3)
    if which == 0:
        data["records"][1]["started_at"] = number
        return
    if which == 1:
        data["records"][1]["finished_at"] = number
        return
    data["claim"]["deadline"] = number


def _spoil_boundary(data, rng):
    """The target is listed on the bound itself, which is not inside the page."""
    poll = data["records"][1]
    poll["page_bound"] = 10
    poll["returned_ids"] = [10]
    if rng.randrange(2) == 0:
        poll["cursor"] = 10


def _spoil_cursor_past(data, rng):
    """The cursor is already past the target, and the page still lists that id."""
    poll = data["records"][1]
    poll["cursor"] = 11 + rng.randrange(0, 20)
    poll["page_bound"] = poll["cursor"] + 5
    poll["returned_ids"] = [10]


def _spoil_chain_holds_target(data, rng):
    """A later page holds the target, but it does not start where the earlier page ended."""
    gap = rng.randrange(1, 9)
    _take(data, _continued())
    data["records"] = [
        data["records"][0],
        {
            "type": "poll",
            "recipient": "room-a",
            "session": "s1",
            "started_at": "2026-11-07T10:05:00Z",
            "finished_at": "2026-11-07T11:00:00Z",
            "cursor": 1,
            "page_bound": 10 - gap,
            "returned_ids": [],
            "has_more": True,
            "completed": True,
            "poller": "running",
        },
        {
            "type": "poll",
            "recipient": "room-a",
            "session": "s1",
            "started_at": "2026-11-07T11:10:00Z",
            "finished_at": "2026-11-07T12:00:00Z",
            "cursor": 10,
            "page_bound": 20,
            "returned_ids": [10],
            "has_more": False,
            "completed": True,
            "poller": "running",
        },
    ]


def _spoil_chain_lists_target_outside(data, rng):
    """A later page lists the target outside its own cursor, and the pages do not meet."""
    skip = rng.randrange(1, 15)
    send = data["records"][0]
    data["records"] = [
        send,
        {
            "type": "poll",
            "recipient": "room-a",
            "session": "s1",
            "started_at": "2026-11-07T10:05:00Z",
            "finished_at": "2026-11-07T11:00:00Z",
            "cursor": 1,
            "page_bound": 10,
            "returned_ids": [],
            "has_more": True,
            "completed": True,
            "poller": "running",
        },
        {
            "type": "poll",
            "recipient": "room-a",
            "session": "s1",
            "started_at": "2026-11-07T11:10:00Z",
            "finished_at": "2026-11-07T12:00:00Z",
            "cursor": 10 + skip,
            "page_bound": 40,
            "returned_ids": [10],
            "has_more": False,
            "completed": True,
            "poller": "running",
        },
    ]


def _spoil_restart_cursor(data, rng):
    """A restart saves a cursor other than the page bound. The next page still lists the target."""
    _take(data, _continued())
    wrong = rng.randrange(0, 80)
    if wrong == 10:
        wrong = 11
    data["records"][2]["persisted_cursor"] = wrong


def _spoil_restart_session(data, rng):
    """A restart names a session the next poll does not resume in."""
    _take(data, _continued())
    data["records"][2]["session_boundary"] = "s" + str(rng.randrange(2, 40))


def _spoil_restart_text(data, rng):
    """A restart saves the cursor as text, not a whole number."""
    _take(data, _continued())
    data["records"][2]["persisted_cursor"] = rng.choice(["10", "010", "²"])


def _spoil_restart_tail(data, rng):
    """A restart has no following poll. The earlier page still lists the target."""
    data["records"].append({"type": "restart", "persisted_cursor": 10, "session_boundary": "s1"})


def _spoil_poller_stopped(data, rng):
    """The poller stopped. The page still lists the target."""
    data["records"][1]["poller"] = "stopped"


def _spoil_start_before_ack(data, rng):
    """The poll starts before the send was acknowledged. The page still lists the target."""
    minute = rng.randrange(0, 59)
    data["records"][1]["started_at"] = f"2026-11-07T09:{minute:02d}:00Z"


def _spoil_has_more(data, rng):
    """The only page says more remains, and it still lists the target."""
    data["records"][1]["has_more"] = True


def _spoil_not_completed(data, rng):
    """The poll is not completed, and it still lists the target."""
    data["records"][1]["completed"] = rng.choice([False, None, "yes"])


def _spoil_deadline_shift(data, rng):
    """The deadline moves off the close. The page still lists the target."""
    hour = rng.randrange(8, 15)
    if hour == 12:
        hour = 13
    data["claim"]["deadline"] = f"2026-11-07T{hour:02d}:00:00Z"


def _spoil_outsider_beside_target(data, rng):
    """The page lists the target and also an id past the page bound."""
    outsider = 20 + rng.randrange(0, 25)
    data["records"][1]["returned_ids"] = [10, outsider]


def _spoil_text_listed_id(data, rng):
    """The page lists the target as text, which is not an id inside the page."""
    if rng.randrange(2) == 0:
        data["records"][1]["returned_ids"] = ["10"]
        return
    data["records"][1]["returned_ids"] = [10, "10"]


def _spoil_finish_before_start(data, rng):
    """The page lists the target and finishes before it started."""
    minute = rng.randrange(0, 4)
    data["records"][1]["finished_at"] = f"2026-11-07T10:0{minute}:00Z"


def _spoil_bad_time_digit(data, rng):
    """A time is a digit the clock cannot read. The page still lists the target."""
    data["records"][1]["started_at"] = "²"


SPOILERS = (
    (_spoil_wake_int, "REJECTED"),
    (_spoil_wake_text, "REJECTED"),
    (_spoil_wake_odd, "NOT COVERED"),
    (_spoil_early_finish, "NOT COVERED"),
    (_spoil_late_finish, "NOT COVERED"),
    (_spoil_same_instant_other_text, "NOT COVERED"),
    (_spoil_mixed_kind, "NOT COVERED"),
    (_spoil_boundary, "NOT COVERED"),
    (_spoil_cursor_past, "NOT COVERED"),
    (_spoil_chain_holds_target, "NOT COVERED"),
    (_spoil_chain_lists_target_outside, "NOT COVERED"),
    (_spoil_restart_cursor, "NOT COVERED"),
    (_spoil_restart_session, "NOT COVERED"),
    (_spoil_restart_text, "NOT COVERED"),
    (_spoil_restart_tail, "NOT COVERED"),
    (_spoil_poller_stopped, "NOT COVERED"),
    (_spoil_start_before_ack, "NOT COVERED"),
    (_spoil_has_more, "NOT COVERED"),
    (_spoil_not_completed, "NOT COVERED"),
    (_spoil_deadline_shift, "NOT COVERED"),
    (_spoil_outsider_beside_target, "NOT COVERED"),
    (_spoil_text_listed_id, "NOT COVERED"),
    (_spoil_finish_before_start, "NOT COVERED"),
    (_spoil_bad_time_digit, "NOT COVERED"),
)


def _save_break(data, index, name, detail):
    """Save one generated record that broke the check, so the same seed can replay it."""
    path = FIXTURES / f"random-break-{SEED}-{index}.json"
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    raise AssertionError(f"seed {SEED} index {index} {name} {detail} file {path.name}")


def test_a_seeded_gap_or_wake_never_prints_covered():
    """A seeded wake is REJECTED and a seeded gap is NOT COVERED. A break is saved."""
    assert silenceproof.check(load("covered.json")) == "COVERED"
    assert silenceproof.check(_continued()) == "COVERED"
    rng = random.Random(SEED)
    for index in range(CASES):
        data = copy.deepcopy(load("covered.json"))
        spoil, expected = SPOILERS[index % len(SPOILERS)]
        spoil(data, rng)
        if rng.randrange(2) == 0:
            _other_room(data)
        try:
            word = silenceproof.check(data)
        except Exception as error:
            _save_break(data, index, spoil.__name__, f"raised {type(error).__name__}")
        if word != expected:
            _save_break(data, index, spoil.__name__, f"printed {word} expected {expected}")


def test_a_line_break_in_a_time_stays_on_one_reason_line(tmp_path, capsys):
    """An accepted time with a line break is shown on one reason line. The verdict stays."""
    def change(data):
        data["records"][1]["finished_at"] = "2026-11-07T10:06:00\nZ"
    path = _covered_copy(tmp_path, "early-break.json", change)
    before = path.read_bytes()
    code = silenceproof.main(["silenceproof", str(path)])
    captured = capsys.readouterr()
    assert path.read_bytes() == before
    assert code == 0
    assert captured.err == ""
    assert captured.out == "NOT COVERED\ngap: the closing page finishes at 2026-11-07T10:06:00\\nZ, not the deadline\n"
    assert silenceproof.check(json.loads(path.read_text(encoding="utf-8"))) == "NOT COVERED"


def _separator_close(tmp_path, capsys, mark, shown, name):
    """One accepted close time with a non-printable separator stays one reason line."""
    def change(data):
        data["records"][1]["finished_at"] = "2026-11-07" + mark + "10:06:00Z"
    path = _covered_copy(tmp_path, name, change)
    before = path.read_bytes()
    code = silenceproof.main(["silenceproof", str(path)])
    captured = capsys.readouterr()
    assert path.read_bytes() == before
    assert mark in json.loads(path.read_text(encoding="utf-8"))["records"][1]["finished_at"]
    assert code == 0
    assert captured.err == ""
    assert captured.out == "NOT COVERED\ngap: the closing page finishes at 2026-11-07" + shown + "10:06:00Z, not the deadline\n"
    assert silenceproof.check(json.loads(path.read_text(encoding="utf-8"))) == "NOT COVERED"


def test_a_line_separator_in_a_time_stays_on_one_reason_line(tmp_path, capsys):
    """U+2028 in an accepted time is shown as text. The verdict stays."""
    _separator_close(tmp_path, capsys, "\u2028", "\\u2028", "line-sep.json")


def test_a_paragraph_separator_in_a_time_stays_on_one_reason_line(tmp_path, capsys):
    """U+2029 in an accepted time is shown as text. The verdict stays."""
    _separator_close(tmp_path, capsys, "\u2029", "\\u2029", "para-sep.json")


def test_a_next_line_in_a_time_stays_on_one_reason_line(tmp_path, capsys):
    """U+0085 in an accepted time is shown as text. The verdict stays."""
    _separator_close(tmp_path, capsys, "\u0085", "\\u0085", "nel.json")


def test_a_zero_width_space_in_a_time_stays_on_one_reason_line(tmp_path, capsys):
    """U+200B in an accepted time is shown as text. The verdict stays."""
    _separator_close(tmp_path, capsys, "\u200b", "\\u200b", "zwsp.json")


def test_the_workflow_pins_proofscope_and_lists_every_test():
    """The GitHub workflow pins ProofScope, and the expected list names every test."""
    workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    assert "UnreachedWorld/proofscope@4630995155f3976ec89f48099beb8abcb68c5a49" in workflow
    assert "expected: expected-tests.txt" in workflow
    assert "--junitxml=build/junit.xml" in workflow
    assert "build/junit.xml" in workflow
    listed = []
    for line in (ROOT / "expected-tests.txt").read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or line.strip() == "":
            continue
        listed.append(line)
    names = []
    for line in (ROOT / "test_silenceproof.py").read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("def test_"):
            name = stripped.split("def ", 1)[1].split("(", 1)[0]
            names.append("test_silenceproof\t" + name)
    assert listed == names
