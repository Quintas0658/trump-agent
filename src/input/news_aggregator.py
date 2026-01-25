"""News aggregator - Fetches from Politico, Axios, and other sources."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import xml.etree.ElementTree as ET
import httpx


@dataclass
class NewsItem:
    """A single news item."""
    title: str
    link: str
    description: str
    published_at: Optional[datetime]
    source: str


class NewsAggregator:
    """Aggregates news from multiple RSS sources.
    
    Focuses on sources that track Trump policy and actions.
    """
    
    RSS_FEEDS = {
        "politico_trump": "https://www.politico.com/rss/trump.xml",
        "politico_politics": "https://www.politico.com/rss/politics.xml",
        "axios": "https://api.axios.com/feed/",
        "reuters_us": "https://www.reuters.com/rssFeed/politicsNews/",
        "ap_politics": "https://rsshub.app/apnews/topics/politics",
    }
    
    def __init__(self):
        self.client = httpx.Client(timeout=30.0)
    
    def fetch_all(self, max_per_source: int = 10) -> list[NewsItem]:
        """Fetch news from all sources."""
        all_items = []
        
        for source_name, feed_url in self.RSS_FEEDS.items():
            try:
                items = self._fetch_feed(feed_url, source_name, max_per_source)
                all_items.extend(items)
            except Exception as e:
                print(f"Failed to fetch {source_name}: {e}")
                continue
        
        # Sort by published date, most recent first
        all_items.sort(
            key=lambda x: x.published_at or datetime.min, 
            reverse=True
        )
        
        return all_items
    
    def fetch_source(self, source_name: str, max_items: int = 10) -> list[NewsItem]:
        """Fetch news from a specific source."""
        feed_url = self.RSS_FEEDS.get(source_name)
        if not feed_url:
            raise ValueError(f"Unknown source: {source_name}")
        
        return self._fetch_feed(feed_url, source_name, max_items)
    
    def _fetch_feed(
        self, 
        feed_url: str, 
        source_name: str, 
        max_items: int
    ) -> list[NewsItem]:
        """Fetch and parse an RSS feed."""
        try:
            response = self.client.get(
                feed_url,
                headers={"User-Agent": "TrumpPolicyAgent/1.0"},
                follow_redirects=True,
            )
            response.raise_for_status()
        except httpx.HTTPError as e:
            print(f"HTTP error fetching {feed_url}: {e}")
            return []
        
        return self._parse_rss(response.text, source_name, max_items)
    
    def _parse_rss(
        self, 
        xml_content: str, 
        source_name: str, 
        max_items: int
    ) -> list[NewsItem]:
        """Parse RSS XML content."""
        items = []
        
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            print(f"Failed to parse RSS: {e}")
            return []
        
        # Handle both RSS 2.0 and Atom formats
        # RSS 2.0
        for item in root.findall(".//item")[:max_items]:
            news_item = self._parse_rss_item(item, source_name)
            if news_item:
                items.append(news_item)
        
        # Atom
        if not items:
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            for entry in root.findall(".//atom:entry", ns)[:max_items]:
                news_item = self._parse_atom_entry(entry, ns, source_name)
                if news_item:
                    items.append(news_item)
        
        return items
    
    def _parse_rss_item(self, item: ET.Element, source_name: str) -> Optional[NewsItem]:
        """Parse an RSS 2.0 item."""
        title = self._get_text(item, "title")
        link = self._get_text(item, "link")
        description = self._get_text(item, "description")
        pub_date_str = self._get_text(item, "pubDate")
        
        if not title:
            return None
        
        published_at = self._parse_date(pub_date_str)
        
        return NewsItem(
            title=title,
            link=link or "",
            description=description or "",
            published_at=published_at,
            source=source_name,
        )
    
    def _parse_atom_entry(
        self, 
        entry: ET.Element, 
        ns: dict, 
        source_name: str
    ) -> Optional[NewsItem]:
        """Parse an Atom entry."""
        title = self._get_text(entry, "atom:title", ns)
        
        # Get link - might be in href attribute
        link_elem = entry.find("atom:link", ns)
        link = link_elem.get("href", "") if link_elem is not None else ""
        
        summary = self._get_text(entry, "atom:summary", ns) or \
                  self._get_text(entry, "atom:content", ns)
        
        updated_str = self._get_text(entry, "atom:updated", ns) or \
                      self._get_text(entry, "atom:published", ns)
        
        if not title:
            return None
        
        published_at = self._parse_date(updated_str)
        
        return NewsItem(
            title=title,
            link=link,
            description=summary or "",
            published_at=published_at,
            source=source_name,
        )
    
    def _get_text(
        self, 
        elem: ET.Element, 
        tag: str, 
        ns: Optional[dict] = None
    ) -> Optional[str]:
        """Get text content of a child element."""
        child = elem.find(tag, ns) if ns else elem.find(tag)
        return child.text.strip() if child is not None and child.text else None
    
    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse various date formats."""
        if not date_str:
            return None
        
        # Common formats
        formats = [
            "%a, %d %b %Y %H:%M:%S %z",  # RSS 2.0
            "%a, %d %b %Y %H:%M:%S %Z",  # RSS 2.0 with timezone name
            "%Y-%m-%dT%H:%M:%S%z",        # Atom/ISO
            "%Y-%m-%dT%H:%M:%SZ",          # UTC
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        return None
    
    def close(self):
        """Close the HTTP client."""
        self.client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()


# Helper to filter Trump-related news
def filter_trump_related(items: list[NewsItem]) -> list[NewsItem]:
    """Filter news items that are likely Trump-related."""
    keywords = [
        "trump", "president", "white house", "administration",
        "executive order", "tariff", "immigration", "border",
        "maga", "republican", "doj", "justice department",
    ]
    
    filtered = []
    for item in items:
        text = (item.title + " " + item.description).lower()
        if any(kw in text for kw in keywords):
            filtered.append(item)
    
    return filtered
