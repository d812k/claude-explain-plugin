"""``TargetMemory``: remember the user's last explicit target pick in a small JSON file."""

import contextlib
import logging
import os
import tempfile
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from explain_selection.domain import Pid, RememberedTarget
from explain_selection.errors import RegistryError

logger = logging.getLogger(__name__)


class _MemoryModel(BaseModel):
    """The on-disk shape of a remembered pick."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    pid: int
    chosen_at_ms: int = Field(alias="chosenAtMs")


class FileTargetMemory:
    """Stores the last remembered target in a single JSON file."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> RememberedTarget | None:
        try:
            raw = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except OSError as exc:
            logger.warning("could not read target memory %s: %s", self._path.name, exc.strerror)
            return None
        try:
            model = _MemoryModel.model_validate_json(raw)
        except ValidationError:
            logger.warning("ignoring invalid target memory %s", self._path.name)
            return None
        return RememberedTarget(Pid(model.pid), model.chosen_at_ms)

    def save(self, remembered: RememberedTarget) -> None:
        self._path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self._path.parent, 0o700)
        payload = (
            _MemoryModel.model_validate(
                {"pid": int(remembered.pid), "chosenAtMs": remembered.chosen_at_ms}
            )
            .model_dump_json(by_alias=True)
            .encode()
        )
        fd, tmp_name = tempfile.mkstemp(
            dir=self._path.parent, prefix=f".{self._path.name}.", suffix=".tmp"
        )
        tmp = Path(tmp_name)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
            os.replace(tmp, self._path)
        except OSError as exc:
            with contextlib.suppress(OSError):
                tmp.unlink()
            raise RegistryError("could not write target memory") from exc


__all__ = ["FileTargetMemory"]
