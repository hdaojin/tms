import subprocess
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from . import samba_sync


@pytest.mark.parametrize("name", ["", "-root", "qa\nadmin", "qa\x00", "group,root", "  name", "0"])
def test_invalid_user_never_reaches_os(name):
    user = SimpleNamespace(username=name)
    with patch.object(samba_sync.subprocess, "run") as run:
        for operation, args in (
            (samba_sync.enable_samba_for_user, ("test",)),
            (samba_sync.change_samba_password, ("test",)),
            (samba_sync.disable_samba_for_user, ()),
            (samba_sync.is_samba_enabled, ()),
        ):
            with pytest.raises(RuntimeError, match="Samba 用户名"):
                operation(user, *args)
        run.assert_not_called()


def test_enable_validates_all_group_names_before_os_changes():
    groups = [SimpleNamespace(name="valid"), SimpleNamespace(name="invalid")]
    user = SimpleNamespace(username="student-01", groups=SimpleNamespace(all=lambda: groups))
    with (
        patch.object(samba_sync.GroupProfile.objects, "get",
                     side_effect=[SimpleNamespace(codename="students"), SimpleNamespace(codename="-root")]),
        patch.object(samba_sync.subprocess, "run") as run,
    ):
        with pytest.raises(RuntimeError, match="Samba 组标识"):
            samba_sync.enable_samba_for_user(user, "test")
        run.assert_not_called()


def test_valid_user_is_passed_as_one_argument():
    user = SimpleNamespace(username="student-01")
    with patch.object(samba_sync.subprocess, "run",
                      return_value=subprocess.CompletedProcess(args=[], returncode=0)) as run:
        assert samba_sync.is_samba_enabled(user)
    assert run.call_args.args == (["sudo", "--", "pdbedit", "-L", "-v", "-u", "student-01"],)
    assert not run.call_args.kwargs.get("shell", False)
