import logging, asyncio
from playwright.async_api import async_playwright
logging.basicConfig(level = logging.INFO, format = "%(asctime)s, [%(levelname)s], %(message)s")
class Async_engine:
    def __init__(self):
        self.playw = None
        self.browser = None
        self.context = None
        self.log = logging.getLogger("AsyncBrowserEngine")
    async def async_engine_init(self, headless=True, exe_path="/usr/bin/chromium"):
        self.log.info("init the engine")
        self.playw = await async_playwright().start()
        self.log.info("browser launch")
        self.browser = await self.playw.chromium.launch(headless=headless, executable_path=exe_path)
    async def spoofed_context(self):
        if not self.browser:
            self.log.info(">>context may be called before launching the browser")
            raise RuntimeError("Browser must be launched earlier")
        self.context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
            viewport= {"width": 1920, "height": 1080})
        self.log.info("getting spoofed context")
        return self.context
    async def shutdown(self):
        self.log.warning("shutting down sub-processes!")
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playw:
            await self.playw.stop()
        self.log.info("All pocesses terminated!")