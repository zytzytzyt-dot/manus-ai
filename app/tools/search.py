import json
import aiohttp
import os
from typing import Dict, List, Optional, Any, ClassVar

from app.tools.base import BaseTool, ToolResult
from app.config.settings import get_settings
from app.utils.logger import get_logger

# Set up logger
logger = get_logger(__name__)

class SearchTool(BaseTool):
    """Tool for performing web searches.
    
    Enables retrieval of information from the web via search engines
    and content extraction from search results.
    """
    name: ClassVar[str] = "search"
    description: ClassVar[str] = "Searches the web for information on a specific query"
    parameters: Dict = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query"
            },
            "num_results": {
                "type": "integer",
                "default": 5,
                "description": "Number of results to return"
            },
            "include_domains": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Domains to include in search"
            },
            "exclude_domains": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Domains to exclude from search"
            },
            "time_period": {
                "type": "string",
                "enum": ["day", "week", "month", "year", "all"],
                "default": "all",
                "description": "Time period for search results"
            }
        },
        "required": ["query"]
    }
    
    search_api_key: str = ""
    search_endpoint: str = ""
    
    def __init__(self):
        super().__init__()
        settings = get_settings()
        
        # 尝试多种可能的配置路径
        self.search_api_key = None
        
        # 直接从settings获取
        if hasattr(settings, 'search_api_key'):
            self.search_api_key = settings.search_api_key
        # 从search配置部分获取
        elif hasattr(settings, 'search') and hasattr(settings.search, 'api_key'):
            self.search_api_key = settings.search.api_key
        # 从环境变量获取
        elif 'SEARCH_API_KEY' in os.environ:
            self.search_api_key = os.environ['SEARCH_API_KEY']
        # 使用LLM API密钥作为后备
        elif hasattr(settings, 'llm') and hasattr(settings.llm, 'api_key'):
            self.search_api_key = settings.llm.api_key
        
        # 如果仍然没有API密钥，记录警告
        if not self.search_api_key:
            logger.warning("未找到搜索API密钥，搜索功能可能不可用")
    
    async def execute(self, **kwargs) -> ToolResult:
        """Execute a web search.
        
        Args:
            **kwargs: Search parameters:
                - query: The search query
                - num_results: Number of results to return
                - include_domains: Domains to include
                - exclude_domains: Domains to exclude
                - time_period: Time period for results
                
        Returns:
            ToolResult with search results
        """
        query = kwargs.get("query")
        if not query:
            return ToolResult(error="No search query provided")
            
        num_results = int(kwargs.get("num_results", 5))
        include_domains = kwargs.get("include_domains", [])
        exclude_domains = kwargs.get("exclude_domains", [])
        time_period = kwargs.get("time_period", "all")
        
        try:
            # Perform search
            results = await self._perform_search(
                query, num_results, include_domains, exclude_domains, time_period
            )
            
            if not results:
                return ToolResult(
                    output=f"No results found for query: {query}",
                    metadata={"query": query, "count": 0}
                )
                
            # Format results
            formatted_results = self._format_results(results)
            
            return ToolResult(
                output=formatted_results,
                metadata={
                    "query": query,
                    "count": len(results),
                    "results": results
                }
            )
            
        except Exception as e:
            logger.error(f"Search error: {str(e)}")
            return ToolResult(error=f"Search failed: {str(e)}")
    
    async def _perform_search(
        self, 
        query: str, 
        num_results: int, 
        include_domains: List[str],
        exclude_domains: List[str],
        time_period: str
    ) -> List[Dict]:
        """Perform web search using search API.
        
        Args:
            query: Search query
            num_results: Number of results to return
            include_domains: Domains to include
            exclude_domains: Domains to exclude
            time_period: Time period for results
            
        Returns:
            List of search results
            
        Raises:
            Exception: If search fails
        """
        # Implement actual search logic based on your preferred API
        # This is a simplified example using a hypothetical search API
        
        if self.search_endpoint and self.search_api_key:
            # Use configured search API
            async with aiohttp.ClientSession() as session:
                params = {
                    "q": query,
                    "num": num_results,
                    "key": self.search_api_key
                }
                
                # Add optional parameters
                if include_domains:
                    params["site"] = " OR ".join(include_domains)
                if time_period != "all":
                    params["time"] = time_period
                
                # Exclude domains with site: operator
                if exclude_domains:
                    exclusions = " -site:".join([""] + exclude_domains)
                    params["q"] += exclusions
                
                async with session.get(self.search_endpoint, params=params) as response:
                    if response.status != 200:
                        raise Exception(f"Search API returned status {response.status}")
                        
                    data = await response.json()
                    return data.get("results", [])
        else:
            # Fallback to simulated search results for demo purposes
            logger.warning("No search API configured - returning simulated results")
            return self._simulate_search_results(query, num_results)
    
    def _simulate_search_results(self, query: str, num_results: int) -> List[Dict]:
        """Simulate search results for demonstration purposes.
        
        Args:
            query: Search query
            num_results: Number of results to return
            
        Returns:
            Simulated search results
        """
        # In a real implementation, this would call an actual search API
        simulated_results = [
            {
                "title": f"Sample Result {i+1} for: {query}",
                "link": f"https://example.com/result{i+1}",
                "snippet": f"This is a simulated search result for the query '{query}'. "
                           f"In a real implementation, this would contain actual search results."
            }
            for i in range(min(num_results, 5))
        ]
        
        return simulated_results
    
    def _format_results(self, results: List[Dict]) -> str:
        """Format search results for display.
        
        Args:
            results: Search result data
            
        Returns:
            Formatted results text
        """
        formatted = "Search Results:\n\n"
        
        for i, result in enumerate(results, 1):
            title = result.get("title", "Untitled")
            link = result.get("link", "")
            snippet = result.get("snippet", "No description available")
            
            formatted += f"{i}. {title}\n"
            formatted += f"   URL: {link}\n"
            formatted += f"   {snippet}\n\n"
            
        return formatted