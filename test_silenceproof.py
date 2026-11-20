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


def test_the_readme_states_the_exit_codes():
    """The README tells a reader to trust the printed verdict, not the exit code."""
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    line = "Read the printed verdict; the exit code is 0 for any verdict and 2 for a usage or file error."
    assert text.count(line) == 1
