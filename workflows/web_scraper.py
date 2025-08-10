"""
Web Scraping Module for AI Automation Factory

Provides functionality for scraping and extracting data from websites.
"""
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import Dict, List, Optional, Set, Tuple
import logging
from pathlib import Path
import json
from loguru import logger
import re

class WebScraper:
    """A class for web scraping operations."""
    
    def __init__(self, base_url: str, max_pages: int = 10, max_concurrent: int = 5):
        """
        Initialize the web scraper.
        
        Args:
            base_url: The starting URL for scraping
            max_pages: Maximum number of pages to scrape
            max_concurrent: Maximum concurrent requests
        """
        self.base_url = base_url
        self.domain = urlparse(base_url).netloc
        self.max_pages = max_pages
        self.max_concurrent = max_concurrent
        self.visited_urls: Set[str] = set()
        self.pages_scraped: int = 0
        self.session: Optional[aiohttp.ClientSession] = None
        self.logger = logger.bind(component="WebScraper", domain=self.domain)
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    async def fetch_page(self, url: str) -> Optional[str]:
        """
        Fetch the HTML content of a web page.
        
        Args:
            url: URL of the page to fetch
            
        Returns:
            HTML content as string, or None if request failed
        """
        if not self.session:
            raise RuntimeError("Session not initialized. Use async with statement.")
            
        try:
            async with self.session.get(url, timeout=10) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    self.logger.warning(f"Failed to fetch {url}: HTTP {response.status}")
                    return None
        except Exception as e:
            self.logger.error(f"Error fetching {url}: {str(e)}")
            return None
    
    def extract_links(self, html: str, base_url: str) -> List[str]:
        """
        Extract all links from HTML content.
        
        Args:
            html: HTML content as string
            base_url: Base URL for resolving relative URLs
            
        Returns:
            List of absolute URLs
        """
        if not html:
            return []
            
        soup = BeautifulSoup(html, 'html.parser')
        links = []
        
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            # Skip empty, anchor, and javascript links
            if not href or href.startswith(('#', 'javascript:', 'mailto:')):
                continue
                
            # Convert relative URLs to absolute
            absolute_url = urljoin(base_url, href)
            
            # Only include links from the same domain
            if urlparse(absolute_url).netloc == self.domain:
                links.append(absolute_url)
                
        return links
    
    async def scrape_page(self, url: str) -> Dict[str, any]:
        """
        Scrape a single page and extract its content.
        
        Args:
            url: URL of the page to scrape
            
        Returns:
            Dictionary containing page data
        """
        if url in self.visited_urls or self.pages_scraped >= self.max_pages:
            return {}
            
        self.visited_urls.add(url)
        self.pages_scraped += 1
        
        self.logger.info(f"Scraping page {self.pages_scraped}/{self.max_pages}: {url}")
        
        html = await self.fetch_page(url)
        if not html:
            return {}
            
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extract page title
        title = soup.title.string if soup.title else "No title"
        
        # Extract main content (simplified - in practice, you'd want more sophisticated content extraction)
        main_content = ""
        content_containers = soup.find_all(['article', 'main', 'div.content'])
        if not content_containers:
            # Fallback to body if no specific containers found
            content_containers = [soup.body] if soup.body else []
            
        for container in content_containers:
            # Remove script and style elements
            for element in container(['script', 'style', 'nav', 'footer', 'header']):
                element.decompose()
            main_content += container.get_text(' ', strip=True) + "\n\n"
        
        # Clean up whitespace
        main_content = ' '.join(main_content.split())
        
        # Extract metadata
        meta = {}
        for meta_tag in soup.find_all('meta'):
            name = meta_tag.get('name') or meta_tag.get('property', '').replace('og:', '')
            if name and meta_tag.get('content'):
                meta[name] = meta_tag['content']
        
        # Extract links for further crawling
        links = self.extract_links(html, url)
        
        return {
            'url': url,
            'title': title,
            'content': main_content,
            'metadata': meta,
            'links': links
        }
    
    async def crawl(self) -> List[Dict[str, any]]:
        """
        Crawl the website starting from the base URL.
        
        Returns:
            List of scraped pages with their content
        """
        if not self.session:
            raise RuntimeError("Session not initialized. Use async with statement.")
            
        queue = asyncio.Queue()
        results = []
        
        # Start with the base URL
        await queue.put(self.base_url)
        
        async def worker():
            while self.pages_scraped < self.max_pages and not queue.empty():
                url = await queue.get()
                
                try:
                    # Scrape the page
                    page_data = await self.scrape_page(url)
                    if page_data:
                        results.append(page_data)
                        
                        # Add new links to the queue
                        for link in page_data.get('links', []):
                            if link not in self.visited_urls and self.pages_scraped < self.max_pages:
                                await queue.put(link)
                except Exception as e:
                    self.logger.error(f"Error processing {url}: {str(e)}")
                finally:
                    queue.task_done()
        
        # Create worker tasks
        tasks = []
        for _ in range(min(self.max_concurrent, self.max_pages)):
            task = asyncio.create_task(worker())
            tasks.append(task)
        
        # Wait for all tasks to complete or max pages reached
        await queue.join()
        
        # Cancel any remaining tasks
        for task in tasks:
            task.cancel()
        
        # Wait for all tasks to be cancelled
        await asyncio.gather(*tasks, return_exceptions=True)
        
        return results
    
    @staticmethod
    def save_results(results: List[Dict[str, any]], output_dir: str = "output") -> str:
        """
        Save scraping results to files.
        
        Args:
            results: List of page data dictionaries
            output_dir: Directory to save results
            
        Returns:
            Path to the output directory
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Save each page as a separate JSON file
        for i, page in enumerate(results):
            filename = f"page_{i+1}_{urlparse(page['url']).path.replace('/', '_') or 'index'}.json"
            filepath = output_path / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(page, f, ensure_ascii=False, indent=2)
        
        # Save a summary file
        summary = {
            'total_pages': len(results),
            'urls': [page['url'] for page in results]
        }
        
        with open(output_path / 'summary.json', 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
            
        return str(output_path.resolve())

# Example usage
async def example_usage():
    """Example of using the WebScraper class."""
    async with WebScraper("https://example.com", max_pages=5) as scraper:
        results = await scraper.crawl()
        output_dir = WebScraper.save_results(results, "scraped_data")
        print(f"Scraped {len(results)} pages. Results saved to: {output_dir}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage())
