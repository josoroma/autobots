"""Which browser a browse drives, Decision 0038 Z1."""

from typing import Literal

# The box's headless Chromium, the default, or the stealth browser: headed Google Chrome in the same
# isolated box.
BrowserKind = Literal["box", "stealth"]
