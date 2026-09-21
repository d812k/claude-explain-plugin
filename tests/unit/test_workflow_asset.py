"""The Automator Quick Action bundle under assets/ matches the hand-built reference."""

import plistlib
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
BUNDLE = REPO / "assets" / "Explain selection.workflow" / "Contents"
SERVICE_NAME = "Explain selection"
SHIM_PATH_FRAGMENT = "/.claude/explain-selection/capture"


def _load(name: str) -> dict[str, Any]:  # Any: plistlib returns untyped nested values
    with (BUNDLE / name).open("rb") as handle:
        loaded: dict[str, Any] = plistlib.load(handle)  # Any: see above
    return loaded


def _service() -> dict[str, Any]:  # Any: see _load
    services = _load("Info.plist")["NSServices"]
    assert len(services) == 1
    return services[0]


def _action() -> dict[str, Any]:  # Any: see _load
    actions = _load("document.wflow")["actions"]
    assert len(actions) == 1
    return actions[0]["action"]


def test_the_service_is_a_workflow_named_explain_selection() -> None:
    service = _service()
    assert service["NSMenuItem"] == {"default": SERVICE_NAME}
    assert service["NSMessage"] == "runWorkflowAsService"


def test_the_service_receives_plain_text_and_returns_nothing() -> None:
    service = _service()
    assert "public.utf8-plain-text" in service["NSSendTypes"]
    assert "NSReturnTypes" not in service


def test_the_single_action_runs_the_shim_with_the_selection_on_stdin() -> None:
    action = _action()
    assert action["BundleIdentifier"] == "com.apple.RunShellScript"
    parameters = action["ActionParameters"]
    assert parameters["inputMethod"] == 0
    assert parameters["shell"] == "/bin/sh"
    assert SHIM_PATH_FRAGMENT in parameters["COMMAND_STRING"]
    assert parameters["COMMAND_STRING"].endswith("--text -")


def test_the_workflow_is_a_services_menu_item_taking_text() -> None:
    metadata = _load("document.wflow")["workflowMetaData"]
    assert metadata["workflowTypeIdentifier"] == "com.apple.Automator.servicesMenu"
    assert metadata["serviceInputTypeIdentifier"] == "com.apple.Automator.text"
    assert metadata["serviceOutputTypeIdentifier"] == "com.apple.Automator.nothing"
