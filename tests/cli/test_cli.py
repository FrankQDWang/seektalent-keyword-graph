import json

import pytest

from seektalent_keyword_graph.cli import build_parser, main


@pytest.mark.parametrize(
    "command",
    [
        "import-jds",
        "extract-surfaces",
        "build-relations",
        "probe-cts",
        "build-snapshot",
        "validate-snapshot",
    ],
)
def test_cli_registers_promised_commands(command):
    help_text = build_parser().format_help()

    assert command in help_text


def test_cli_help_returns_zero(capsys):
    assert main(["--help"]) == 0

    assert "keyword-graph" in capsys.readouterr().out


@pytest.mark.parametrize(
    "command",
    [
        "import-jds",
        "extract-surfaces",
        "build-relations",
        "probe-cts",
        "build-snapshot",
        "validate-snapshot",
    ],
)
def test_cli_subcommand_help_returns_zero(command, capsys):
    assert main([command, "--help"]) == 0

    assert command in capsys.readouterr().out


def test_probe_cts_dry_run_outputs_payload(capsys):
    assert main(["probe-cts", "--dry-run", "Python"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["keyword"] == "Python"
    assert payload["page"] == 1
    assert payload["pageSize"] == 1


def test_probe_cts_defaults_to_dry_run_payload(capsys):
    assert main(["probe-cts", "Python"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["keyword"] == "Python"
