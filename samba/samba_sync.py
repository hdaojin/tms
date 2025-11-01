import subprocess


def _run(cmd: list[str], input_bytes: bytes | None = None) -> subprocess.CompletedProcess:
    full = ["sudo", "--"] + cmd
    return subprocess.run(
        full,
        input=input_bytes,
        capture_output=True,
        check=False,
    )

def __exists_unix_group(group: str) -> bool:
    result = _run(["getent", "group", group])
    return result.returncode == 0

def __create_unix_group(group: str) -> None:
    if not __exists_unix_group(group):
        _run (["groupadd", group])

def _exists_unix_user(username: str) -> bool:
    result = _run(["id", "-u", username])
    return result.returncode == 0

def _create_unix_user(username: str, password: str, primary_group: str | None, create_home: bool, shell: str = "/sbin/nologin") -> None:
    if not _exists_unix_user(username):
        args = ["useradd", username]
        if primary_group:
            args += ["-g", primary_group]
        if create_home:
            args += ["-m"]
        if shell:
            args += ["-s", shell]
        _run(args)

def _ensure_user_in_groups(username: str, groups: list[str]) -> None:
    if not groups:
        return
    _run(["usermod", "-aG", ",".join(groups), username])

def _exists_samba_user(username: str) -> bool:
    result = _run(["pdbedit", "-L", "-v", "-u", username])
    return result.returncode == 0

def _set_samba_user_password(username: str, password: str, create_if_missing: bool = True) -> None:
    cmd = ["smbpasswd", "-s"]
    if create_if_missing and not _exists_samba_user(username):
        cmd.append("-a")
    cmd.append(username)
    pw_input = f"{password}\n{password}\n".encode("utf-8")
    result= _run(cmd, input_bytes=pw_input)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode("utf-8") or result.stdout.decode("utf-8") or "Unknown error setting Samba password")


def enable_samba_for_user(user, password:str) -> dict:
    username = user.username

    django_group = list(user.groups.values_list("name", flat=True))
    primary_group = django_group[0] if django_group else None

    for group in django_group:
        __create_unix_group(group)

    pre_exists = _exists_unix_user(username)
    _create_unix_user(username, password, primary_group, create_home=False, shell="/sbin/nologin")


    extend_groups = django_group[1:] if primary_group else django_group
    _ensure_user_in_groups(username, extend_groups)

    _set_samba_user_password(username, password, create_if_missing=True)
    return {
        "username": username,
        "created": not pre_exists,
    }

def is_samba_enabled(user) -> bool:
    return _exists_samba_user(user.username)


def change_samba_password(user, new_password: str) -> None:
    username = user.username
    if not _exists_unix_user(username):
        raise RuntimeError(f"Unix user '{username}' does not exist")
    if not _exists_samba_user(username):
        raise RuntimeError(f"Samba user '{username}' does not exist")
    _set_samba_user_password(username, new_password, create_if_missing=False)


def disable_samba_for_user(user) -> None:
    username = user.username
    if _exists_samba_user(username):
        _run(["smbpasswd", "-x", username])
