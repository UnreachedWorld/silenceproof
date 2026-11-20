# What this file does: it checks SilenceProof on fictional records.
# Nothing here uses the network.

import json
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


def test_the_readme_states_the_exit_codes():
    """The README tells a reader to trust the printed verdict, not the exit code."""
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    line = "Read the printed verdict; the exit code is 0 for any verdict and 2 for a usage or file error."
    assert text.count(line) == 1
