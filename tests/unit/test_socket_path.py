"""Socket path resolution mirrors what Claude Code does on disk."""

from explain_selection.domain import (
    MAX_SOCKET_PATH_BYTES,
    Pid,
    candidate_socket_paths,
    pid_from_socket_path,
)


def test_primary_path_uses_xdg_runtime_dir() -> None:
    paths = candidate_socket_paths(Pid(2268544), {"XDG_RUNTIME_DIR": "/run/user/501"}, 501)
    assert paths == (
        "/run/user/501/cc-socks/2268544.sock",
        "/tmp/cc-socks-501/2268544.sock",
    )


def test_primary_path_defaults_to_tmp_without_xdg_runtime_dir() -> None:
    paths = candidate_socket_paths(Pid(5982), {}, 501)
    assert paths[0] == "/tmp/cc-socks/5982.sock"


def test_empty_xdg_runtime_dir_counts_as_unset() -> None:
    paths = candidate_socket_paths(Pid(7), {"XDG_RUNTIME_DIR": ""}, 0)
    assert paths[0] == "/tmp/cc-socks/7.sock"


def test_overlong_primary_path_is_replaced_by_uid_fallback() -> None:
    long_dir = "/" + "x" * MAX_SOCKET_PATH_BYTES
    paths = candidate_socket_paths(Pid(1), {"XDG_RUNTIME_DIR": long_dir}, 42)
    assert paths == ("/tmp/cc-socks-42/1.sock",)


def test_undecodable_runtime_dir_bytes_do_not_raise() -> None:
    # Python surfaces undecodable environment bytes as lone surrogates (surrogateescape).
    paths = candidate_socket_paths(Pid(9), {"XDG_RUNTIME_DIR": "/\udc80run"}, 501)
    assert paths == ("/\udc80run/cc-socks/9.sock", "/tmp/cc-socks-501/9.sock")


def test_overlong_undecodable_runtime_dir_is_replaced_by_uid_fallback() -> None:
    long_dir = "/" + "\udc80" * MAX_SOCKET_PATH_BYTES
    paths = candidate_socket_paths(Pid(1), {"XDG_RUNTIME_DIR": long_dir}, 42)
    assert paths == ("/tmp/cc-socks-42/1.sock",)


def test_pid_is_read_back_from_a_socket_path() -> None:
    assert pid_from_socket_path("/run/user/501/cc-socks/2268544.sock") == 2268544


def test_non_socket_paths_yield_no_pid() -> None:
    assert pid_from_socket_path("/tmp/cc-socks/notapid.sock") is None
    assert pid_from_socket_path("/tmp/cc-socks/123.json") is None
    assert pid_from_socket_path("") is None
