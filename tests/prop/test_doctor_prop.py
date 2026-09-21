"""Property tests: ``evaluate`` is total and every non-ok check tells the user what to do."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from explain_selection.domain import (
    ClaudeFacts,
    DoctorFacts,
    FileFacts,
    InboundPolicy,
    MacFacts,
    Pid,
    RootSource,
    RuntimeFacts,
    SessionFacts,
    SessionKind,
    SessionStatus,
    checks_ok,
    evaluate,
)

policies: st.SearchStrategy[InboundPolicy | None] = st.sampled_from(
    ["accept", "hold", "refuse", None]
)
root_sources: st.SearchStrategy[RootSource] = st.sampled_from(["environment", "shim", "checkout"])
roots = st.sampled_from(["/plugins/explain-selection", "/moved/elsewhere"])
versions = st.sampled_from(["0.1.0", "0.2.0", ""])
template_paths = st.sampled_from(["/users/me/explain-prompt.txt", "/tmp/my prompt.txt"])


@st.composite
def file_facts(draw: st.DrawFn) -> FileFacts:
    exists = draw(st.booleans())
    return FileFacts(
        exists=exists,
        mode=draw(st.integers(min_value=0, max_value=0o777)) if exists else None,
        is_dir=exists and draw(st.booleans()),
        is_socket=exists and draw(st.booleans()),
        is_executable=exists and draw(st.booleans()),
        readable=exists and draw(st.booleans()),
    )


@st.composite
def runtime_facts(draw: st.DrawFn) -> RuntimeFacts:
    return RuntimeFacts(
        home=draw(file_facts()),
        venv_python=draw(file_facts()),
        installed_version=draw(st.one_of(st.none(), versions)),
        plugin_version=draw(versions),
        shim=draw(file_facts()),
        shim_plugin_root=draw(st.one_of(st.none(), roots)),
        plugin_root=draw(roots),
        root_source=draw(root_sources),
        config_present=draw(st.booleans()),
        template_path=draw(template_paths),
        template=draw(file_facts()),
        template_has_placeholder=draw(st.booleans()),
    )


@st.composite
def session_facts(draw: st.DrawFn) -> SessionFacts:
    registered = draw(st.booleans())
    return SessionFacts(
        pid=Pid(draw(st.integers(min_value=1, max_value=99_999))),
        status=draw(st.sampled_from(list(SessionStatus))),
        kind=draw(st.sampled_from(list(SessionKind))),
        registered=registered,
        tmux=draw(st.one_of(st.none(), st.text(max_size=8))),
        socket=draw(file_facts()) if registered else None,
        age_ms=draw(st.integers(min_value=0, max_value=10**12)),
    )


@st.composite
def claude_facts(draw: st.DrawFn) -> ClaudeFacts:
    return ClaudeFacts(
        sessions=tuple(draw(st.lists(session_facts(), max_size=5))),
        stale_entries=draw(st.integers(min_value=0, max_value=20)),
        cross_session_inbound=draw(policies),
        plugin_enabled=draw(st.booleans()),
        agents_error=draw(st.one_of(st.none(), st.text(max_size=20))),
    )


@st.composite
def mac_facts(draw: st.DrawFn) -> MacFacts:
    return MacFacts(
        bundle=draw(file_facts()),
        shortcut_status=draw(st.one_of(st.none(), st.text(max_size=30))),
        osascript_found=draw(st.booleans()),
    )


@st.composite
def doctor_facts(draw: st.DrawFn) -> DoctorFacts:
    return DoctorFacts(
        runtime=draw(runtime_facts()),
        claude=draw(claude_facts()),
        mac=draw(st.one_of(st.none(), mac_facts())),
    )


@pytest.mark.prop
@given(doctor_facts())
def test_evaluate_is_total_and_every_non_ok_check_carries_a_fix(facts: DoctorFacts) -> None:
    checks = evaluate(facts)
    assert len(checks) == 13 + len(facts.claude.sessions)
    for check in checks:
        assert check.name
        assert check.detail
        if check.status in ("warn", "fail"):
            assert check.fix
        else:
            assert check.fix is None
    assert checks_ok(checks) == all(check.status != "fail" for check in checks)


@pytest.mark.prop
@given(doctor_facts())
def test_the_mac_checks_are_skipped_exactly_when_there_are_no_mac_facts(facts: DoctorFacts) -> None:
    mac_checks = evaluate(facts)[-3:]
    assert [check.name for check in mac_checks] == ["services-bundle", "shortcut", "osascript"]
    assert all(check.status == "skip" for check in mac_checks) == (facts.mac is None)
