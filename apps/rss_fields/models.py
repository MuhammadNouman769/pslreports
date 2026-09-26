from django.db import models
from django.utils import timezone
import uuid
from apps.utilities.models import CoreModel


class RSSFeedSource(CoreModel):
    """Model to store RSS feed sources"""
    SOURCE_CHOICES = [
        ('bbc_sport', 'BBC Sport Football'),
        ('espn_soccer', 'ESPN Soccer'),
        ('sky_sports', 'Sky Sports Football'),
        ('guardian', 'Guardian Football'),
    ]
    
    name = models.CharField(max_length=100)
    source_type = models.CharField(max_length=20, choices=SOURCE_CHOICES, unique=True)
    feed_url = models.URLField(max_length=500)
    is_active = models.BooleanField(default=True)
    last_fetched = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'RSS Feed Source'
        verbose_name_plural = 'RSS Feed Sources'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.source_type})"
    
    @property
    def feed_count(self):
        """Return the number of feeds from this source"""
        return self.feed_items.count()


class RSSFeedItem(CoreModel):
    """Model to store individual RSS feed items"""
    source = models.ForeignKey(RSSFeedSource, on_delete=models.CASCADE, related_name='feed_items')
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    content = models.TextField(blank=True)
    link = models.URLField(max_length=1000)
    author = models.CharField(max_length=200, blank=True)
    category = models.CharField(max_length=100, blank=True)
    guid = models.CharField(max_length=500, unique=True)
    published_date = models.DateTimeField()
    fetched_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = 'RSS Feed Item'
        verbose_name_plural = 'RSS Feed Items'
        ordering = ['-published_date']
        indexes = [
            models.Index(fields=['-published_date']),
            models.Index(fields=['source', '-published_date']),
            models.Index(fields=['is_read']),
            models.Index(fields=['is_archived']),
        ]
    
    def __str__(self):
        return self.title
    
    @property
    def short_title(self):
        """Return truncated title for display"""
        return self.title[:100] + '...' if len(self.title) > 100 else self.title
    
    @property
    def short_description(self):
        """Return truncated description for display"""
        return self.description[:200] + '...' if len(self.description) > 200 else self.description
    
    def mark_as_read(self):
        """Mark the feed item as read"""
        self.is_read = True
        self.save(update_fields=['is_read'])
    
    def archive(self):
        """Archive the feed item"""
        self.is_archived = True
        self.save(update_fields=['is_archived'])


class FeedFetchLog(CoreModel):
    """Model to log RSS feed fetching activities"""
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('error', 'Error'),
        ('partial', 'Partial Success'),
    ]
    
    source = models.ForeignKey(RSSFeedSource, on_delete=models.CASCADE, related_name='fetch_logs')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    items_fetched = models.PositiveIntegerField(default=0)
    items_new = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    fetch_duration = models.FloatField(help_text='Duration in seconds', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Feed Fetch Log'
        verbose_name_plural = 'Feed Fetch Logs'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.source.name} - {self.status} - {self.created_at}"