from celery import shared_task
from django.utils import timezone
import logging
from .services import RSSFeedManager
from .models import RSSFeedSource, RSSFeedItem

logger = logging.getLogger(__name__)


@shared_task(bind=True, name='rss_feeds.fetch_all_feeds')
def fetch_all_feeds_task(self):
    """
    Celery task to fetch all active RSS feeds
    """
    try:
        logger.info("Starting RSS feed fetch task")
        manager = RSSFeedManager()
        results = manager.fetch_all_feeds()
        
        total_items_fetched = 0
        total_items_new = 0
        successful_sources = 0
        
        for source_name, (success, message, items_fetched, items_new) in results.items():
            if success:
                successful_sources += 1
                total_items_fetched += items_fetched
                total_items_new += items_new
                logger.info(f"✓ {source_name}: {message}")
            else:
                logger.error(f"✗ {source_name}: {message}")
        
        logger.info(f"RSS feed fetch completed. "
                   f"Sources: {successful_sources}/{len(results)}, "
                   f"Items fetched: {total_items_fetched}, "
                   f"New items: {total_items_new}")
        
        return {
            'status': 'success',
            'sources_processed': len(results),
            'sources_successful': successful_sources,
            'total_items_fetched': total_items_fetched,
            'total_items_new': total_items_new,
            'results': results
        }
        
    except Exception as e:
        logger.error(f"Error in RSS feed fetch task: {e}")
        self.retry(countdown=300, max_retries=3)  # Retry after 5 minutes, max 3 retries
        return {
            'status': 'error',
            'error': str(e)
        }


@shared_task(bind=True, name='rss_feeds.fetch_specific_source')
def fetch_specific_source_task(self, source_type: str):
    """
    Celery task to fetch RSS feed from a specific source
    """
    try:
        logger.info(f"Starting RSS feed fetch for source: {source_type}")
        manager = RSSFeedManager()
        success, message, items_fetched, items_new = manager.fetch_specific_source(source_type)
        
        if success:
            logger.info(f"✓ {source_type}: {message}")
        else:
            logger.error(f"✗ {source_type}: {message}")
        
        return {
            'status': 'success' if success else 'error',
            'source_type': source_type,
            'message': message,
            'items_fetched': items_fetched,
            'items_new': items_new
        }
        
    except Exception as e:
        logger.error(f"Error fetching RSS feed for {source_type}: {e}")
        self.retry(countdown=300, max_retries=3)
        return {
            'status': 'error',
            'source_type': source_type,
            'error': str(e)
        }


@shared_task(name='rss_feeds.initialize_sources')
def initialize_sources_task():
    """
    Celery task to initialize default RSS feed sources
    """
    try:
        logger.info("Initializing RSS feed sources")
        manager = RSSFeedManager()
        manager.initialize_sources()
        
        # Count created sources
        source_count = RSSFeedSource.objects.count()
        logger.info(f"RSS feed sources initialized. Total sources: {source_count}")
        
        return {
            'status': 'success',
            'sources_count': source_count
        }
        
    except Exception as e:
        logger.error(f"Error initializing RSS feed sources: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }


@shared_task(name='rss_feeds.cleanup_old_feeds')
def cleanup_old_feeds_task(days_to_keep: int = 30):
    """
    Celery task to cleanup old RSS feed items
    """
    try:
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=days_to_keep)
        
        # Archive old feed items
        old_items = RSSFeedItem.objects.filter(
            published_date__lt=cutoff_date,
            is_archived=False
        )
        
        items_to_archive = old_items.count()
        old_items.update(is_archived=True)
        
        # Delete very old archived items (older than 90 days)
        very_old_cutoff = timezone.now() - timedelta(days=90)
        very_old_items = RSSFeedItem.objects.filter(
            published_date__lt=very_old_cutoff,
            is_archived=True
        )
        
        items_to_delete = very_old_items.count()
        very_old_items.delete()
        
        logger.info(f"Cleanup completed. "
                   f"Archived: {items_to_archive} items, "
                   f"Deleted: {items_to_delete} items")
        
        return {
            'status': 'success',
            'items_archived': items_to_archive,
            'items_deleted': items_to_delete
        }
        
    except Exception as e:
        logger.error(f"Error in RSS feed cleanup task: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }


@shared_task(name='rss_feeds.mark_as_read')
def mark_as_read_task(feed_item_id: str):
    """
    Celery task to mark a feed item as read
    """
    try:
        manager = RSSFeedManager()
        success = manager.mark_as_read(feed_item_id)
        
        return {
            'status': 'success' if success else 'error',
            'feed_item_id': feed_item_id,
            'marked_as_read': success
        }
        
    except Exception as e:
        logger.error(f"Error marking feed item as read: {e}")
        return {
            'status': 'error',
            'feed_item_id': feed_item_id,
            'error': str(e)
        }


@shared_task(name='rss_feeds.archive_feed_item')
def archive_feed_item_task(feed_item_id: str):
    """
    Celery task to archive a feed item
    """
    try:
        manager = RSSFeedManager()
        success = manager.archive_feed_item(feed_item_id)
        
        return {
            'status': 'success' if success else 'error',
            'feed_item_id': feed_item_id,
            'archived': success
        }
        
    except Exception as e:
        logger.error(f"Error archiving feed item: {e}")
        return {
            'status': 'error',
            'feed_item_id': feed_item_id,
            'error': str(e)
        }


@shared_task(name='rss_feeds.health_check')
def health_check_task():
    """
    Celery task to perform health check on RSS feed sources
    """
    try:
        # Check active sources
        active_sources = RSSFeedSource.objects.filter(is_active=True)
        total_sources = active_sources.count()
        
        # Check recent activity
        recent_feeds = RSSFeedItem.objects.filter(
            fetched_at__gte=timezone.now() - timezone.timedelta(hours=24)
        ).count()
        
        # Check for sources that haven't been fetched recently
        stale_sources = active_sources.filter(
            last_fetched__lt=timezone.now() - timezone.timedelta(hours=6)
        ).count()
        
        health_status = 'healthy'
        if stale_sources > 0:
            health_status = 'warning'
        if total_sources == 0:
            health_status = 'error'
        
        return {
            'status': 'success',
            'health_status': health_status,
            'total_sources': total_sources,
            'recent_feeds_24h': recent_feeds,
            'stale_sources': stale_sources
        }
        
    except Exception as e:
        logger.error(f"Error in RSS feed health check: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }