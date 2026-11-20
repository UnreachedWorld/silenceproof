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


def test_a_strange_digit_is_not_covered_and_does_not_crash(capsys):
    """A digit that int() refuses prints NOT COVERED and no traceback."""
    assert silenceproof.check(load("odd-digit-wake.json")) == "NOT COVERED"
    code = silenceproof.main(["silenceproof", str(FIXTURES / "odd-digit-wake.json")])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == "NOT COVERED\n"
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


def test_each_verdict_exits_zero(capsys):
    """COVERED, REJECTED and NOT COVERED each print the verdict and exit 0."""
    expected = (
        ("covered.json", "COVERED"),
        ("wake.json", "REJECTED"),
        ("backward-bound.json", "NOT COVERED"),
    )
    for name, word in expected:
        code = silenceproof.main(["silenceproof", str(FIXTURES / name)])
        captured = capsys.readouterr()
        assert code == 0
        assert captured.out == word + "\n"
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
    assert captured.out == "NOT COVERED\n"
    assert captured.err == ""
    assert "Traceback" not in captured.out


def test_the_readme_states_the_exit_codes():
    """The README tells a reader to trust the printed verdict, not the exit code."""
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    line = "Read the printed verdict; the exit code is 0 for any verdict and 2 for a usage or file error."
    assert text.count(line) == 1


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
