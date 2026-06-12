import os
import sys
import subprocess
import logging
from .base import Renderer

logger = logging.getLogger(__name__)

def playwright_installed() -> bool:
    try:
        import playwright
        # Also check if chromium is installed
        # A simple check is to see if the playwright browsers path exists
        # But importing playwright is the first step
        return True
    except ImportError:
        return False

def run_playwright_install() -> None:
    logger.info("Installing Playwright chromium browser... this may take a moment.")
    subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])

class PlaywrightRenderer(Renderer):
    def render_pdf(self, html: str, output_path: str) -> None:
        from playwright.sync_api import sync_playwright
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_content(html)
            page.pdf(path=output_path, format="A4", print_background=True)
            browser.close()
