from django.shortcuts import render, get_object_or_404
from apps.stories.models import Story,StoryTag
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_not_required
from django.db.models import Q, Count
from django.core.paginator import Paginator
from django.template.loader import render_to_string

def story_list(request, tag_slug=None):
    ''' display list stories with published '''
    stories = Story.objects.filter(
        status='published'
    ).select_related('author').prefetch_related('tags')

    query = request.GET.get('q')

    if query:
        stories = stories.filter(
            Q(title__icontains=query) |
            Q(content__icontains=query) |
            Q(author__first_name__icontains=query) |
            Q(author__last_name__icontains=query) |
            Q(author__username__icontains=query) |
            Q(tags__name__icontains=query)
        ).distinct()

    tag = None
    if tag_slug:
        tag = get_object_or_404(StoryTag, slug=tag_slug)
        stories = stories.filter(tags=tag)

    paginator = Paginator(stories, 8)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # AJAX LOAD MORE
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return render(
            request,
            'stories/partials/story_cards.html',
            {'stories': page_obj}
        )

    return render(request, 'stories/stories_list.html', {
        'page_obj': page_obj,
        'stories': page_obj,
        'tag': tag,
        'query': query,
        'results_count': stories.count()
    })


def blog_detail(request, slug):
    '''display singal story published with related content'''
    
    story = get_object_or_404(Story, slug=slug)

    context = {
        'story':story
    }
    return render(request, 'blog-details.html', context=context)


def index_view(request):
    """View for the home/index page"""
    banner_stories = Story.objects.filter(
        status='published'
    ).select_related('author').prefetch_related('tags').order_by('-created_at')[:3]

    return render(request, 'index.html', {
        'banner_stories': banner_stories
    })


def author_view(request):
    """View for the author page"""
    return render(request, 'author.html')


def blog_details_vie(request):
    """View for the blog details page"""
    return render(request, 'blog-details.html')

def coming_soon_view(request):
    """View for the coming soon page"""
    return render(request, 'coming-soon.html')


def error_view(request):
    """View for the error page"""
    return render(request, 'error.html')