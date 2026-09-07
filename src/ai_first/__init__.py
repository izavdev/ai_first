"""Development import compatibility; production code lives in the setup assets."""
from pathlib import Path

__path__ = [str(Path(__file__).resolve().parents[2] / 'skills/setup-ai-first/assets/ai_first')]
from .version import PACKAGE_VERSION, POLICY_REVISION
