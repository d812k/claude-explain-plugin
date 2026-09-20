"""Property tests: socket path resolution round-trips and stays within limits."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from explain_selection.domain import (
    MAX_SOCKET_PATH_BYTES,
    Pid,
    candidate_socket_paths,
    pid_from_socket_path,
)

pids = st.integers(min_value=1, max_value=2**22).map(Pid)
uids = st.integers(min_value=0, max_value=2**31)
runtime_dirs = st.one_of(
    st.none(),
    st.text(alphabet=st.characters(blacklist_characters="/\x00"), min_size=1, max_size=120).map(
        lambda s: "/" + s
    ),
)


@pytest.mark.prop
@given(pid=pids, uid=uids, runtime_dir=runtime_dirs)
def test_every_candidate_round_trips_to_the_same_pid(
    pid: Pid, uid: int, runtime_dir: str | None
) -> None:
    env = {} if runtime_dir is None else {"XDG_RUNTIME_DIR": runtime_dir}
    for path in candidate_socket_paths(pid, env, uid):
        assert pid_from_socket_path(path) == pid


@pytest.mark.prop
@given(pid=pids, uid=uids, runtime_dir=runtime_dirs)
def test_first_candidate_never_exceeds_the_sockaddr_limit(
    pid: Pid, uid: int, runtime_dir: str | None
) -> None:
    env = {} if runtime_dir is None else {"XDG_RUNTIME_DIR": runtime_dir}
    first = candidate_socket_paths(pid, env, uid)[0]
    assert len(first.encode()) <= MAX_SOCKET_PATH_BYTES
