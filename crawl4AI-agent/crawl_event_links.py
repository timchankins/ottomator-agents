import os
import sys
import json
import asyncio
import requests
from xml.etree import ElementTree
from typing import List, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse
from dotenv import load_dotenv

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from openai import AsyncOpenAI
from supabase import create_client, Client

load_dotenv()

# Initialize OpenAI and Supabase clients
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY")
)

@dataclass
class ProcessedChunk:
    url: str
    chunk_number: int
    title: str
    summary: str
    content: str
    metadata: Dict[str, Any]
    embedding: List[float]

def chunk_text(text: str, chunk_size: int = 5000) -> List[str]:
    print("""Split text into chunks, respecting code blocks and paragraphs.""")
    # ...existing code from crawl_chi_conferences.py...

async def get_title_and_summary(chunk: str, url: str) -> Dict[str, str]:
    print("""Extract title and summary using GPT-4.""")
    # ...existing code from crawl_chi_conferences.py...

async def get_embedding(text: str) -> List[float]:
    print("""Get embedding vector from OpenAI.""")
    # ...existing code from crawl_chi_conferences.py...

async def process_chunk(chunk: str, chunk_number: int, url: str) -> ProcessedChunk:
    print("""Process a single chunk of text.""")
    # ...existing code from crawl_chi_conferences.py...

async def insert_chunk(chunk: ProcessedChunk):
    print("""Insert a processed chunk into Supabase.""")
    # ...existing code from crawl_chi_conferences.py...

async def process_and_store_document(url: str, markdown: str):
    print("""Process a document and store its chunks in parallel.""")
    # ...existing code from crawl_chi_conferences.py...

async def crawl_event_links(urls: List[str], max_concurrent: int = 5):
    print("""Crawl event link domains but stop at third domain.""")
    browser_config = BrowserConfig(
        headless=True,
        verbose=False,
        extra_args=["--disable-gpu", "--disable-dev-shm-usage", "--no-sandbox"],
    )
    crawl_config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)

    # Create the crawler instance
    crawler = AsyncWebCrawler(config=browser_config)
    await crawler.start()

    try:
        # Create a semaphore to limit concurrency
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_url(url: str):
            async with semaphore:
                result = await crawler.arun(
                    url=url,
                    config=crawl_config,
                    session_id="session1"
                )
                if result.success:
                    print(f"Successfully crawled: {url}")
                    await process_and_store_document(url, result.markdown_v2.raw_markdown)
                else:
                    print(f"Failed: {url} - Error: {result.error_message}")
        
        # Process all URLs in parallel with limited concurrency
        await asyncio.gather(*[process_url(url) for url in urls])
    finally:
        await crawler.close()

def get_event_links_from_conference(conference_url: str) -> List[str]:
    print("""Extract event links from a conference summary page.""")
    try:
        response = requests.get(conference_url)
        response.raise_for_status()
        
        # Parse the HTML and extract event links
        # This is a placeholder; you need to implement the actual extraction logic
        event_links = ["https://tei.acm.org/2025/", "https://humanrobotinteraction.org/2025/"]
        
        return event_links
    except Exception as e:
        print(f"Error fetching conference page: {e}")
        return []

async def main():
    # Get conference URLs
    conference_urls = ["https://sigchi.org/conferences/upcoming/"]
    
    # Extract event links from each conference URL
    event_links = []
    for conference_url in conference_urls:
        event_links.extend(get_event_links_from_conference(conference_url))
    
    if not event_links:
        print("No event links found to crawl")
        return
    
    print(f"Found {len(event_links)} event links to crawl")
    await crawl_event_links(event_links)

if __name__ == "__main__":
    asyncio.run(main())