from typing import Protocol

class Renderer(Protocol):
    def render_pdf(self, html: str, output_path: str) -> None:
        ...

def get_renderer() -> Renderer:
    from .antigravity_renderer import antigravity_browser_available, AntigravityRenderer
    
    if antigravity_browser_available():
        return AntigravityRenderer()
    
    from .playwright_renderer import PlaywrightRenderer, playwright_installed, run_playwright_install
    if not playwright_installed():
        run_playwright_install()
    
    return PlaywrightRenderer()
