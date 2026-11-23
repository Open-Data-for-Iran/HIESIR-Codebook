"""The command line: every command is listed, loads, and parses its options."""

import pytest

from hiesir_codebook.cli import LAZY, app, main


def test_help_lists_every_command(capsys):
    assert main(["--help"]) == 0
    out = capsys.readouterr().out
    for name in ["build", "extract", *(name for name, *_ in LAZY)]:
        assert name in out, name


@pytest.mark.parametrize("name", [name for name, *_ in LAZY])
def test_each_lazy_command_loads(name, capsys):
    """A lazy command is imported only when it runs: --help on it catches a bad import path."""
    assert main([name, "--help"]) == 0
    assert "Usage:" in capsys.readouterr().out


def test_options_reach_the_function():
    from pathlib import Path

    _, bound, _ = app.parse_args(
        ["correct", "--check", "--occurrence", "a.csv", "b.csv"], print_error=False, exit_on_error=False
    )
    assert bound.kwargs == {"check": True, "occurrence": [Path("a.csv"), Path("b.csv")]}
    _, bound, _ = app.parse_args(["build", "--no-extract"], print_error=False, exit_on_error=False)
    assert bound.kwargs == {"no_extract": True}
    _, bound, _ = app.parse_args(["pdfs", "download", "1386", "1390"], print_error=False, exit_on_error=False)
    assert bound.args == ([1386, 1390],)
