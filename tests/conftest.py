"""The only conftest. Hypothesis profiles; nothing autouse."""

import os

from hypothesis import settings

settings.register_profile("fast", max_examples=25)
settings.register_profile("ci", max_examples=300)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "fast"))
