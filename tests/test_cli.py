import json

import pytest

from conquest import cli, config


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "conquest.db")
    monkeypatch.setattr(config, "INBOX_DIR", tmp_path / "inbox")
    monkeypatch.setattr(config, "IMPORTED_DIR", tmp_path / "inbox" / "imported")
    (tmp_path / "inbox").mkdir()
    return tmp_path


def test_import_moves_file_and_reports(data_dir, sample_batch, capsys):
    path = data_dir / "inbox" / "run.json"
    path.write_text(json.dumps(sample_batch), encoding="utf-8")

    assert cli.main(["import", str(path), "--no-geocode"]) == 0

    out = capsys.readouterr().out
    assert "2 new events" in out
    assert "+ Sample Comic Convention" in out
    assert not path.exists()
    assert (data_dir / "inbox" / "imported" / "run.json").exists()


def test_bad_file_is_not_imported(data_dir, sample_batch, capsys):
    sample_batch["series"][0]["size_tier"] = "huge"
    path = data_dir / "inbox" / "bad.json"
    path.write_text(json.dumps(sample_batch), encoding="utf-8")

    assert cli.main(["import", str(path), "--no-geocode"]) == 1

    err = capsys.readouterr().err
    assert "NOT imported" in err
    assert "series[0].size_tier" in err
    assert path.exists()  # left in place to be fixed


def test_context_prints_json(data_dir, capsys):
    assert cli.main(["context", "--category", "robots"]) == 0
    context = json.loads(capsys.readouterr().out)
    assert context["suggested_next"]["categories"] == ["engineering"]


def test_unknown_category_word(data_dir, capsys):
    assert cli.main(["context", "--category", "cooking"]) == 2
    assert "Unknown category" in capsys.readouterr().err
