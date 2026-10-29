from types import SimpleNamespace

import pytest

from scripts import migrate_internal_legacy as migrator


def test_migration_refuses_live_source_before_accessing_connections(monkeypatch, tmp_path):
    class NoConnections:
        def __getitem__(self, key):
            pytest.fail("拒绝生产源库前不应访问任何数据库连接")

    monkeypatch.setattr(migrator, "connections", NoConnections())
    monkeypatch.setattr("sys.argv", ["migrate_internal_legacy.py", "--source-database", "tmsdb",
                                    "--target-database", "tms", "--report", str(tmp_path / "report.json"),
                                    "--apply"])
    with pytest.raises(SystemExit) as error:
        migrator.main()
    assert error.value.code == 2
    assert not (tmp_path / "report.json").exists()


@pytest.mark.parametrize("target", ["other", "tms_legacy_restore_online"])
def test_migration_refuses_wrong_or_identical_target(monkeypatch, tmp_path, target, capsys):
    connection = SimpleNamespace(settings_dict={"NAME": target, "PASSWORD": "never-print-this-secret"})
    monkeypatch.setattr(migrator, "connections", {"default": connection})
    monkeypatch.setattr("sys.argv", ["migrate_internal_legacy.py", "--source-database",
                                    "tms_legacy_restore_online", "--target-database",
                                    "tms" if target == "other" else target,
                                    "--report", str(tmp_path / "report.json"), "--apply"])
    with pytest.raises(SystemExit) as error:
        migrator.main()
    assert error.value.code == 2
    assert "never-print-this-secret" not in capsys.readouterr().err
    assert not (tmp_path / "report.json").exists()
