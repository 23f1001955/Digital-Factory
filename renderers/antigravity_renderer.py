import logging
from .base import Renderer

logger = logging.getLogger(__name__)


def antigravity_browser_available() -> bool:
    """Antigravity not yet integrated — falls through to Playwright."""
    return False


class AntigravityRenderer(Renderer):
    def render_pdf(self, html: str, output_path: str) -> None:
        raise NotImplementedError(
            "Antigravity renderer adapter is not yet implemented."
        )
