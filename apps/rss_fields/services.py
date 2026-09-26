import feedparser
import requests
from datetime import datetime
from django.utils import timezone
from django.db import transaction
import logging
from typing import Dict, List, Optional, Tuple
from .models import RSSFeedSource, RSSFeedItem, FeedFetchLog

logger = logging.getLogger(__name__)


class RSSFeedFetcher:
    """Service class for fetching RSS feeds from various sources"""
    
    # Default RSS feed URLs for the specified sources
    DEFAULT_FEED_URLS = {
        'bbc_sport': 'https://feeds.bbci.co.uk/sport/football/rss.xml',
        'espn_soccer': 'https://www.espn.com/espn/rss/soccer/news',
        'sky_sports': 'https://www.skysports.com/rss/0,20514,11661,00.xml',
        'guardian': 'https://www.theguardian.com/football/rss',
    }
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'GoalLineReport-RSS-Fetcher/1.0'
        })
    
    def fetch_feed(self, source: RSSFeedSource) -> Tuple[bool, str, int, int]:
        """
        Fetch RSS feed from a specific source
        
        Returns:
            Tuple of (success, message, items_fetched, items_new)
        """
        start_time = timezone.now()
        items_fetched = 0
        items_new = 0
        error_message = ""
        
        try:
            # Fetch the RSS feed
            response = self.session.get(source.feed_url, timeout=self.timeout)
            response.raise_for_status()
            
            # Parse the RSS feed
            feed = feedparser.parse(response.content)
            
            if feed.bozo:
                logger.warning(f"Feed parsing warning for {source.name}: {feed.bozo_exception}")
            
            items_fetched = len(feed.entries)
            
            # Process each feed item
            for entry in feed.entries:
                if self._process_feed_item(source, entry):
                    items_new += 1
            
            # Update source last_fetched timestamp
            source.last_fetched = timezone.now()
            source.save(update_fields=['last_fetched'])
            
            success = True
            message = f"Successfully fetched {items_fetched} items, {items_new} new"
            
        except requests.RequestException as e:
            success = False
            error_message = f"Network error: {str(e)}"
            logger.error(f"Network error fetching {source.name}: {e}")
            
        except Exception as e:
            success = False
            error_message = f"Unexpected error: {str(e)}"
            logger.error(f"Error fetching {source.name}: {e}")
        
        # Calculate fetch duration
        fetch_duration = (timezone.now() - start_time).total_seconds()
        
        # Log the fetch attempt
        self._log_fetch_attempt(source, success, items_fetched, items_new, error_message, fetch_duration)
        
        return success, error_message or message, items_fetched, items_new
    
    def _process_feed_item(self, source: RSSFeedSource, entry) -> bool:
        """
        Process a single feed item and save it to database
        
        Returns:
            True if item was new, False if it already existed
        """
        try:
            # Extract GUID (unique identifier)
            guid = self._extract_guid(entry)
            if not guid:
                logger.warning(f"No GUID found for entry: {entry.get('title', 'Unknown')}")
                return False
            
            # Check if item already exists
            if RSSFeedItem.objects.filter(guid=guid).exists():
                return False
            
            # Extract and clean data
            title = self._clean_text(entry.get('title', ''))
            description = self._clean_text(entry.get('description', ''))
            content = self._clean_text(entry.get('content', [{}])[0].get('value', '')) if entry.get('content') else ''
            link = entry.get('link', '')
            author = self._clean_text(entry.get('author', ''))
            category = self._clean_text(entry.get('category', ''))
            
            # Parse published date
            published_date = self._parse_date(entry.get('published', ''))
            if not published_date:
                published_date = timezone.now()
            
            # Create the feed item
            with transaction.atomic():
                RSSFeedItem.objects.create(
                    source=source,
                    title=title,
                    description=description,
                    content=content,
                    link=link,
                    author=author,
                    category=category,
                    guid=guid,
                    published_date=published_date
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing feed item: {e}")
            return False
    
    def _extract_guid(self, entry) -> Optional[str]:
        """Extract GUID from feed entry"""
        # Try different possible GUID fields
        guid = entry.get('id') or entry.get('guid') or entry.get('link')
        return str(guid) if guid else None
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text content"""
        if not text:
            return ""
        
        # Remove HTML tags and normalize whitespace
        import re
        from html import unescape
        
        # Unescape HTML entities
        text = unescape(text)
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def _parse_date(self, date_string: str) -> Optional[datetime]:
        """Parse date string to datetime object"""
        if not date_string:
            return None
        
        try:
            # Try parsing with feedparser's date parser
            import time
            parsed_time = time.strptime(date_string, '%a, %d %b %Y %H:%M:%S %z')
            return datetime.fromtimestamp(time.mktime(parsed_time), tz=timezone.utc)
        except (ValueError, TypeError):
            try:
                # Try alternative date formats
                from dateutil import parser
                return parser.parse(date_string)
            except:
                logger.warning(f"Could not parse date: {date_string}")
                return None
    
    def _log_fetch_attempt(self, source: RSSFeedSource, success: bool, 
                          items_fetched: int, items_new: int, 
                          error_message: str, fetch_duration: float):
        """Log the fetch attempt to database"""
        status = 'success' if success else 'error'
        if success and items_new < items_fetched:
            status = 'partial'
        
        FeedFetchLog.objects.create(
            source=source,
            status=status,
            items_fetched=items_fetched,
            items_new=items_new,
            error_message=error_message,
            fetch_duration=fetch_duration
        )
    
    def fetch_all_active_sources(self) -> Dict[str, Tuple[bool, str, int, int]]:
        """
        Fetch feeds from all active sources
        
        Returns:
            Dictionary mapping source names to (success, message, items_fetched, items_new)
        """
        results = {}
        active_sources = RSSFeedSource.objects.filter(is_active=True)
        
        for source in active_sources:
            logger.info(f"Fetching feed from {source.name}")
            success, message, items_fetched, items_new = self.fetch_feed(source)
            results[source.name] = (success, message, items_fetched, items_new)
        
        return results
    
    def create_default_sources(self):
        """Create default RSS feed sources if they don't exist"""
        for source_type, feed_url in self.DEFAULT_FEED_URLS.items():
            source_name = dict(RSSFeedSource.SOURCE_CHOICES)[source_type]
            
            RSSFeedSource.objects.get_or_create(
                source_type=source_type,
                defaults={
                    'name': source_name,
                    'feed_url': feed_url,
                    'is_active': True
                }
            )
        
        logger.info("Default RSS feed sources created/verified")


class RSSFeedManager:
    """Manager class for RSS feed operations"""
    
    def __init__(self):
        self.fetcher = RSSFeedFetcher()
    
    def initialize_sources(self):
        """Initialize default RSS feed sources"""
        self.fetcher.create_default_sources()
    
    def fetch_all_feeds(self):
        """Fetch all active RSS feeds"""
        return self.fetcher.fetch_all_active_sources()
    
    def fetch_specific_source(self, source_type: str):
        """Fetch feed from a specific source type"""
        try:
            source = RSSFeedSource.objects.get(source_type=source_type, is_active=True)
            return self.fetcher.fetch_feed(source)
        except RSSFeedSource.DoesNotExist:
            logger.error(f"Source {source_type} not found or not active")
            return False, "Source not found", 0, 0
    
    def get_recent_feeds(self, limit: int = 50, source_type: str = None):
        """Get recent feed items"""
        queryset = RSSFeedItem.objects.select_related('source').filter(is_archived=False)
        
        if source_type:
            queryset = queryset.filter(source__source_type=source_type)
        
        return queryset.order_by('-published_date')[:limit]
    
    def mark_as_read(self, feed_item_id: str):
        """Mark a feed item as read"""
        try:
            feed_item = RSSFeedItem.objects.get(id=feed_item_id)
            feed_item.mark_as_read()
            return True
        except RSSFeedItem.DoesNotExist:
            return False
    
    def archive_feed_item(self, feed_item_id: str):
        """Archive a feed item"""
        try:
            feed_item = RSSFeedItem.objects.get(id=feed_item_id)
            feed_item.archive()
            return True
        except RSSFeedItem.DoesNotExist:
            return False