from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from .models import RSSFeedSource, RSSFeedItem, FeedFetchLog
from .services import RSSFeedManager
from .tasks import fetch_all_feeds_task, mark_as_read_task, archive_feed_item_task

manager = RSSFeedManager()


def rss_feed_list(request):
    """Display list of RSS feed items"""
    # Get filter parameters
    source_type = request.GET.get('source')
    category = request.GET.get('category')
    search = request.GET.get('search')
    unread_only = request.GET.get('unread') == 'true'
    
    # Build queryset
    queryset = RSSFeedItem.objects.select_related('source').filter(is_archived=False)
    
    # Apply filters
    if source_type:
        queryset = queryset.filter(source__source_type=source_type)
    
    if category:
        queryset = queryset.filter(category__icontains=category)
    
    if search:
        queryset = queryset.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search) |
            Q(author__icontains=search)
        )
    
    if unread_only:
        queryset = queryset.filter(is_read=False)
    
    # Order by published date
    queryset = queryset.order_by('-published_date')
    
    # Pagination
    paginator = Paginator(queryset, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get available sources and categories for filters
    sources = RSSFeedSource.objects.filter(is_active=True)
    categories = RSSFeedItem.objects.filter(
        is_archived=False
    ).values_list('category', flat=True).distinct().exclude(category='')
    
    # Get stats
    total_feeds = RSSFeedItem.objects.filter(is_archived=False).count()
    unread_feeds = RSSFeedItem.objects.filter(is_archived=False, is_read=False).count()
    
    context = {
        'page_obj': page_obj,
        'sources': sources,
        'categories': categories,
        'total_feeds': total_feeds,
        'unread_feeds': unread_feeds,
        'current_source': source_type,
        'current_category': category,
        'current_search': search,
        'unread_only': unread_only,
    }
    
    return render(request, 'rss_feeds/feed_list.html', context)


def rss_feed_detail(request, feed_id):
    """Display detailed view of a single RSS feed item"""
    feed_item = get_object_or_404(RSSFeedItem, id=feed_id, is_archived=False)
    
    # Mark as read if not already
    if not feed_item.is_read:
        feed_item.mark_as_read()
    
    # Get related feeds from same source
    related_feeds = RSSFeedItem.objects.filter(
        source=feed_item.source,
        is_archived=False
    ).exclude(id=feed_item.id).order_by('-published_date')[:5]
    
    context = {
        'feed_item': feed_item,
        'related_feeds': related_feeds,
    }
    
    return render(request, 'rss_feeds/feed_detail.html', context)


@login_required
def rss_feed_sources(request):
    """Display and manage RSS feed sources"""
    sources = RSSFeedSource.objects.all().order_by('name')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'fetch_all':
            # Trigger background task to fetch all feeds
            task = fetch_all_feeds_task.delay()
            messages.success(request, f'RSS feed fetch started. Task ID: {task.id}')
            return redirect('rss_feeds:sources')
        
        elif action == 'toggle_source':
            source_id = request.POST.get('source_id')
            try:
                source = RSSFeedSource.objects.get(id=source_id)
                source.is_active = not source.is_active
                source.save()
                status = 'activated' if source.is_active else 'deactivated'
                messages.success(request, f'Source "{source.name}" {status}.')
            except RSSFeedSource.DoesNotExist:
                messages.error(request, 'Source not found.')
    
    # Get recent fetch logs
    recent_logs = FeedFetchLog.objects.select_related('source').order_by('-created_at')[:10]
    
    context = {
        'sources': sources,
        'recent_logs': recent_logs,
    }
    
    return render(request, 'rss_feeds/sources.html', context)


@login_required
def rss_feed_stats(request):
    """Display RSS feed statistics"""
    # Get basic stats
    total_sources = RSSFeedSource.objects.count()
    active_sources = RSSFeedSource.objects.filter(is_active=True).count()
    total_feeds = RSSFeedItem.objects.count()
    unread_feeds = RSSFeedItem.objects.filter(is_read=False).count()
    
    # Get feeds by source
    feeds_by_source = []
    for source in RSSFeedSource.objects.all():
        feed_count = source.feed_items.count()
        unread_count = source.feed_items.filter(is_read=False).count()
        feeds_by_source.append({
            'source': source,
            'total_feeds': feed_count,
            'unread_feeds': unread_count,
            'last_fetched': source.last_fetched,
        })
    
    # Get recent activity
    recent_feeds = RSSFeedItem.objects.select_related('source').order_by('-fetched_at')[:10]
    
    # Get fetch logs
    fetch_logs = FeedFetchLog.objects.select_related('source').order_by('-created_at')[:20]
    
    context = {
        'total_sources': total_sources,
        'active_sources': active_sources,
        'total_feeds': total_feeds,
        'unread_feeds': unread_feeds,
        'feeds_by_source': feeds_by_source,
        'recent_feeds': recent_feeds,
        'fetch_logs': fetch_logs,
    }
    
    return render(request, 'rss_feeds/stats.html', context)


def mark_as_read_ajax(request, feed_id):
    """AJAX endpoint to mark a feed item as read"""
    if request.method == 'POST':
        try:
            feed_item = RSSFeedItem.objects.get(id=feed_id)
            feed_item.mark_as_read()
            return JsonResponse({'status': 'success'})
        except RSSFeedItem.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Feed item not found'}, status=404)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)


def archive_feed_ajax(request, feed_id):
    """AJAX endpoint to archive a feed item"""
    if request.method == 'POST':
        try:
            feed_item = RSSFeedItem.objects.get(id=feed_id)
            feed_item.archive()
            return JsonResponse({'status': 'success'})
        except RSSFeedItem.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Feed item not found'}, status=404)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)


def fetch_feeds_ajax(request):
    """AJAX endpoint to trigger RSS feed fetching"""
    if request.method == 'POST':
        try:
            # Trigger background task
            task = fetch_all_feeds_task.delay()
            return JsonResponse({
                'status': 'success',
                'message': 'RSS feed fetch started',
                'task_id': task.id
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)


def rss_feed_api(request):
    """API endpoint to get RSS feeds in JSON format"""
    # Get filter parameters
    source_type = request.GET.get('source')
    limit = int(request.GET.get('limit', 50))
    offset = int(request.GET.get('offset', 0))
    
    # Build queryset
    queryset = RSSFeedItem.objects.select_related('source').filter(is_archived=False)
    
    if source_type:
        queryset = queryset.filter(source__source_type=source_type)
    
    # Apply pagination
    feeds = queryset.order_by('-published_date')[offset:offset + limit]
    
    # Serialize data
    feed_data = []
    for feed in feeds:
        feed_data.append({
            'id': str(feed.id),
            'title': feed.title,
            'description': feed.description,
            'link': feed.link,
            'author': feed.author,
            'category': feed.category,
            'published_date': feed.published_date.isoformat(),
            'source': {
                'name': feed.source.name,
                'source_type': feed.source.source_type,
            },
            'is_read': feed.is_read,
        })
    
    return JsonResponse({
        'status': 'success',
        'feeds': feed_data,
        'total': queryset.count(),
        'limit': limit,
        'offset': offset,
    })