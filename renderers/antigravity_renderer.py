import logging
from .base import Renderer

logger = logging.getLogger(__name__)

def antigravity_browser_available() -> bool:
    """
    Probes for the Antigravity browser hook.
    Since this is currently unverified, we safely return False.
    """
    try:
        # Placeholder for actual probe logic
        # For now, we assume it's not available to force fallback
        return False
    except Exception as e:
        logger.debug(f"Antigravity probe failed: {e}")
        return False

class AntigravityRenderer(Renderer):
    def render_pdf(self, html: str, output_path: str) -> None:
        raise NotImplementedError("Antigravity renderer adapter is not yet implemented.")
