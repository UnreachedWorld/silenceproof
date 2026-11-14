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
