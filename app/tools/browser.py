import asyncio
import base64
import json
import os
from typing import Dict, List, Optional, Union
from typing import ClassVar

from pydantic import Field

from app.tools.base import BaseTool, ToolResult
from app.config.settings import get_settings
from app.utils.logger import get_logger

# Set up logger
logger = get_logger(__name__)

class BrowserTool(BaseTool):
    """Tool for browser automation and web interaction.
    
    Provides capabilities for navigating web pages, interacting with elements,
    extracting content, and searching the web.
    """
    name: ClassVar[str] = "browser"
    description: ClassVar[str] = "Automates browser interactions to navigate websites, fill forms, and extract content"
    parameters: Dict = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "go_to_url",
                    "click_element",
                    "input_text",
                    "scroll_down",
                    "scroll_up",
                    "scroll_to_text",
                    "extract_content",
                    "search",
                    "get_screenshot",
                    "back",
                    "forward",
                    "refresh"
                ],
                "description": "The browser action to perform"
            },
            "url": {
                "type": "string",
                "description": "URL for navigation or search"
            },
            "selector": {
                "type": "string",
                "description": "CSS selector for target element"
            },
            "text": {
                "type": "string",
                "description": "Text to input or search for"
            },
            "amount": {
                "type": "integer",
                "description": "Amount to scroll in pixels"
            },
            "goal": {
                "type": "string",
                "description": "Content extraction goal"
            }
        },
        "required": ["action"]
    }
    
    # Browser state
    browser: Optional[any] = Field(default=None, exclude=True)
    page: Optional[any] = Field(default=None, exclude=True)
    browser_lock: asyncio.Lock = Field(default_factory=asyncio.Lock)
    
    async def execute(self, **kwargs) -> ToolResult:
        """Execute a browser action.
        
        Args:
            **kwargs: Action parameters including:
                - action: The browser action to perform
                - url: URL for navigation
                - selector: Element selector
                - text: Text to input
                - amount: Scroll amount
                - goal: Content extraction goal
                
        Returns:
            ToolResult with action output or error
        """
        async with self.browser_lock:
            # Initialize browser if needed
            if not self.browser:
                await self._initialize_browser()
            
            action = kwargs.get("action")
            if not action:
                return ToolResult(error="No action specified")
            
            try:
                # Route to appropriate action handler
                if action == "go_to_url":
                    return await self._go_to_url(kwargs.get("url"))
                elif action == "click_element":
                    return await self._click_element(kwargs.get("selector"))
                elif action == "input_text":
                    return await self._input_text(kwargs.get("selector"), kwargs.get("text"))
                elif action == "scroll_down" or action == "scroll_up":
                    direction = 1 if action == "scroll_down" else -1
                    amount = kwargs.get("amount", 300)
                    return await self._scroll(direction * amount)
                elif action == "scroll_to_text":
                    return await self._scroll_to_text(kwargs.get("text"))
                elif action == "extract_content":
                    return await self._extract_content(kwargs.get("goal"))
                elif action == "search":
                    return await self._web_search(kwargs.get("text"))
                elif action == "get_screenshot":
                    return await self._get_screenshot()
                elif action == "back":
                    return await self._go_back()
                elif action == "forward":
                    return await self._go_forward()
                elif action == "refresh":
                    return await self._refresh()
                else:
                    return ToolResult(error=f"Unknown browser action: {action}")
            except Exception as e:
                logger.error(f"Browser action error: {str(e)}")
                return ToolResult(error=f"Browser action failed: {str(e)}")
    
    async def _initialize_browser(self):
        """Initialize the browser and page objects."""
        try:
            # Use a try-import to handle browser dependencies
            try:
                from playwright.async_api import async_playwright
                
                settings = get_settings()
                self._playwright = await async_playwright().start()
                
                # Configure browser launch options
                browser_type = settings.browser_type.lower()
                launch_options = {
                    "headless": settings.browser_headless
                }
                
                # Launch appropriate browser
                if browser_type == "chromium":
                    self.browser = await self._playwright.chromium.launch(**launch_options)
                elif browser_type == "firefox":
                    self.browser = await self._playwright.firefox.launch(**launch_options)
                elif browser_type == "webkit":
                    self.browser = await self._playwright.webkit.launch(**launch_options)
                else:
                    # Default to chromium
                    self.browser = await self._playwright.chromium.launch(**launch_options)
                
                # Create context and page
                context = await self.browser.new_context(
                    viewport={"width": 1280, "height": 800}
                )
                self.page = await context.new_page()
                logger.info("Browser initialized successfully")
                
            except ImportError:
                logger.error("Playwright not installed. Install with: pip install playwright")
                raise RuntimeError("Browser automation dependencies not installed")
                
        except Exception as e:
            logger.error(f"Failed to initialize browser: {str(e)}")
            raise RuntimeError(f"Browser initialization failed: {str(e)}")
    
    async def _go_to_url(self, url: str) -> ToolResult:
        """Navigate to a URL.
        
        Args:
            url: The URL to navigate to
            
        Returns:
            ToolResult with navigation result
        """
        if not url:
            return ToolResult(error="No URL provided")
        
        try:
            await self.page.goto(url, wait_until="domcontentloaded")
            title = await self.page.title()
            return ToolResult(
                output=f"Navigated to {url}\nPage title: {title}",
                metadata={"url": url, "title": title}
            )
        except Exception as e:
            return ToolResult(error=f"Navigation failed: {str(e)}")
    
    async def _click_element(self, selector: str) -> ToolResult:
        """Click an element on the page.
        
        Args:
            selector: CSS selector for the element to click
            
        Returns:
            ToolResult with click result
        """
        if not selector:
            return ToolResult(error="No element selector provided")
        
        try:
            # Wait for element to be available
            await self.page.wait_for_selector(selector, state="visible", timeout=5000)
            await self.page.click(selector)
            
            # Wait for any resulting navigation or network activity
            await self.page.wait_for_load_state("networkidle")
            
            # Check for new page title after click
            title = await self.page.title()
            url = self.page.url
            
            return ToolResult(
                output=f"Clicked element '{selector}'\nCurrent page: {title}",
                metadata={"selector": selector, "title": title, "url": url}
            )
        except Exception as e:
            return ToolResult(error=f"Click failed: {str(e)}")
    
    async def _input_text(self, selector: str, text: str) -> ToolResult:
        """Input text into a form element.
        
        Args:
            selector: CSS selector for the input element
            text: Text to input
            
        Returns:
            ToolResult with input result
        """
        if not selector:
            return ToolResult(error="No element selector provided")
        if not text:
            return ToolResult(error="No text provided")
        
        try:
            # Wait for element and type text
            await self.page.wait_for_selector(selector, state="visible", timeout=5000)
            await self.page.fill(selector, text)
            
            return ToolResult(
                output=f"Input text '{text}' into element '{selector}'",
                metadata={"selector": selector, "text": text}
            )
        except Exception as e:
            return ToolResult(error=f"Text input failed: {str(e)}")
    
    async def _scroll(self, amount: int) -> ToolResult:
        """Scroll the page.
        
        Args:
            amount: Pixels to scroll (positive for down, negative for up)
            
        Returns:
            ToolResult with scroll result
        """
        try:
            await self.page.evaluate(f"window.scrollBy(0, {amount})")
            direction = "down" if amount > 0 else "up"
            
            return ToolResult(
                output=f"Scrolled {direction} by {abs(amount)} pixels",
                metadata={"amount": amount}
            )
        except Exception as e:
            return ToolResult(error=f"Scroll failed: {str(e)}")
    
    async def _scroll_to_text(self, text: str) -> ToolResult:
        """Scroll to text on the page.
        
        Args:
            text: Text to scroll to
            
        Returns:
            ToolResult with scroll result
        """
        if not text:
            return ToolResult(error="No text provided")
        
        try:
            # Find text using XPath
            xpath = f"//*[contains(text(), '{text}')]"
            element = await self.page.wait_for_selector(xpath, timeout=5000)
            
            if element:
                await element.scroll_into_view_if_needed()
                
                return ToolResult(
                    output=f"Scrolled to text '{text}'",
                    metadata={"text": text}
                )
            else:
                return ToolResult(error=f"Text '{text}' not found on page")
                
        except Exception as e:
            return ToolResult(error=f"Scroll to text failed: {str(e)}")
    
    async def _extract_content(self, goal: str) -> ToolResult:
        """Extract content from the page based on a goal.
        
        Args:
            goal: Content extraction goal
            
        Returns:
            ToolResult with extracted content
        """
        if not goal:
            return ToolResult(error="No extraction goal provided")
        
        try:
            # Get page content
            html_content = await self.page.content()
            
            # Use basic extraction for now
            # In a real implementation, use more sophisticated extraction
            # techniques or LLM-based extraction
            
            # Extract title
            title = await self.page.title()
            
            # Extract visible text
            text_content = await self.page.evaluate('''() => {
                return Array.from(document.body.querySelectorAll('p, h1, h2, h3, h4, h5, li, span, div'))
                    .filter(el => el.textContent.trim() && getComputedStyle(el).display != 'none')
                    .map(el => el.textContent.trim())
                    .join('\\n');
            }''')
            
            # Limit text content length
            max_length = 10000
            if len(text_content) > max_length:
                text_content = text_content[:max_length] + "... (content truncated)"
                
            # Extract links
            links = await self.page.evaluate('''() => {
                return Array.from(document.links)
                    .filter(link => link.href && link.href.startsWith('http'))
                    .map(link => ({ text: link.textContent.trim(), href: link.href }))
                    .filter(link => link.text)
                    .slice(0, 20);  // Limit to 20 links
            }''')
            
            extracted_content = {
                "title": title,
                "url": self.page.url,
                "text_content": text_content,
                "links": links
            }
            
            return ToolResult(
                output=f"Extracted content from page with goal: {goal}",
                metadata={"extracted_content": extracted_content, "goal": goal}
            )
            
        except Exception as e:
            return ToolResult(error=f"Content extraction failed: {str(e)}")
    
    async def _web_search(self, query: str) -> ToolResult:
        """Perform a web search.
        
        Args:
            query: Search query
            
        Returns:
            ToolResult with search result
        """
        if not query:
            return ToolResult(error="No search query provided")
        
        try:
            # Navigate to search engine and perform search
            search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            await self.page.goto(search_url, wait_until="domcontentloaded")
            
            # Wait for search results
            await self.page.wait_for_selector("div[data-header-feature]", timeout=10000)
            
            # Extract search results
            search_results = await self.page.evaluate('''() => {
                const results = [];
                const elements = document.querySelectorAll('div[data-header-feature] div.g');
                
                for (const el of elements) {
                    const titleEl = el.querySelector('h3');
                    const linkEl = el.querySelector('a');
                    const snippetEl = el.querySelector('div[data-content-feature="1"]');
                    
                    if (titleEl && linkEl) {
                        results.push({
                            title: titleEl.textContent,
                            link: linkEl.href,
                            snippet: snippetEl ? snippetEl.textContent : ''
                        });
                    }
                }
                
                return results.slice(0, 5);  // Return top 5 results
            }''')
            
            if search_results:
                output = f"Search results for '{query}':\n\n"
                for i, result in enumerate(search_results, 1):
                    output += f"{i}. {result['title']}\n"
                    output += f"   {result['link']}\n"
                    output += f"   {result['snippet']}\n\n"
                    
                return ToolResult(
                    output=output,
                    metadata={"query": query, "results": search_results}
                )
            else:
                return ToolResult(
                    output=f"No search results found for '{query}'",
                    metadata={"query": query, "results": []}
                )
                
        except Exception as e:
            return ToolResult(error=f"Search failed: {str(e)}")
    
    async def _get_screenshot(self) -> ToolResult:
        """Take a screenshot of the current page.
        
        Returns:
            ToolResult with screenshot as base64
        """
        try:
            # Capture screenshot as bytes
            screenshot_bytes = await self.page.screenshot(full_page=False, type="jpeg", quality=80)
            
            # Convert to base64
            base64_screenshot = base64.b64encode(screenshot_bytes).decode("utf-8")
            
            return ToolResult(
                output="Screenshot captured",
                base64_image=base64_screenshot,
                metadata={"url": self.page.url}
            )
        except Exception as e:
            return ToolResult(error=f"Screenshot failed: {str(e)}")
    
    async def _go_back(self) -> ToolResult:
        """Navigate back in browser history.
        
        Returns:
            ToolResult with navigation result
        """
        try:
            await self.page.go_back()
            await self.page.wait_for_load_state("domcontentloaded")
            
            title = await self.page.title()
            return ToolResult(
                output=f"Navigated back to: {title}",
                metadata={"url": self.page.url, "title": title}
            )
        except Exception as e:
            return ToolResult(error=f"Back navigation failed: {str(e)}")
    
    async def _go_forward(self) -> ToolResult:
        """Navigate forward in browser history.
        
        Returns:
            ToolResult with navigation result
        """
        try:
            await self.page.go_forward()
            await self.page.wait_for_load_state("domcontentloaded")
            
            title = await self.page.title()
            return ToolResult(
                output=f"Navigated forward to: {title}",
                metadata={"url": self.page.url, "title": title}
            )
        except Exception as e:
            return ToolResult(error=f"Forward navigation failed: {str(e)}")
    
    async def _refresh(self) -> ToolResult:
        """Refresh the current page.
        
        Returns:
            ToolResult with refresh result
        """
        try:
            await self.page.reload()
            await self.page.wait_for_load_state("domcontentloaded")
            
            title = await self.page.title()
            return ToolResult(
                output=f"Refreshed page: {title}",
                metadata={"url": self.page.url, "title": title}
            )
        except Exception as e:
            return ToolResult(error=f"Page refresh failed: {str(e)}")
    
    async def cleanup(self):
        """Clean up browser resources."""
        if self.browser:
            try:
                await self.browser.close()
                await self._playwright.stop()
                self.browser = None
                self.page = None
                logger.info("Browser resources cleaned up")
            except Exception as e:
                logger.error(f"Browser cleanup error: {str(e)}")
