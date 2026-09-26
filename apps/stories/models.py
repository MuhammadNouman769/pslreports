""" =========== IMPORTS ============ """
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.urls import reverse
from django.utils.text import slugify
from apps.utilities.models import CoreModel
from ckeditor_uploader.fields import RichTextUploadingField # type: ignore



""" ============= Story Model ============"""
class Story(CoreModel):
    '''Model for story/news field'''

    class StoryStatus(models.TextChoices):
        Draft = 'draft', 'Draft'
        REVIEW = 'review', 'Under Review'
        PUBLISHED = 'published', 'published'
        REJECTED = 'rejected', 'Rejected'
        CANCEL = 'cancel', 'Cancel'
    class PostType(models.TextChoices):
        TRENDING = 'trending', 'Trending Now'
        BANNER = 'banner', 'Banner'
        NORMAL = 'normal', 'Normal Post'


    ''' ------- core fields -------- '''
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    content = RichTextUploadingField(max_length=1000)
    image = models.ImageField(upload_to='stories/%Y/%m/%d', blank=True, null=True)
    summery_image = models.ImageField(upload_to='summries/%Y/%m/%d', blank=True, null=True)
    
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='stories')
    status = models.CharField(max_length=10, choices=StoryStatus.choices,default=StoryStatus.Draft)
    post_type = models.CharField(max_length=10, choices=PostType.choices, default=PostType.NORMAL)
    tags = models.ManyToManyField("StoryTag", related_name='stories')
    summery = models.TextField(max_length=1000, blank=True, help_text="Brief summery of story")
    published_at = models.DateTimeField(null=True, blank=True)

    '''Review work flow'''
    reviewed_by = models.ForeignKey(User,on_delete=models.SET_NULL,blank=True,null=True,related_name='rewieved_stories'
    )
    reviewed_at = models.DateTimeField(blank=True, null=True)
    review_notes = models.TextField(blank=True, help_text="Review comments from chief editor")
    views_count = models.PositiveIntegerField(default=0)
    likes_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Stories'
    
    
    
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        if self.status == 'published' and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)
    

    def can_edit(self, user):
        if not user.is_authenticated:
            return False
        if hasattr(user, "profile") and getattr(user.profile, "is_chief_editor", False):
            return True
        return self.author == user and getattr(user.profile, "is_editor", False)
    
    def can_review(self, user):
        return user.is_authenticated and hasattr(user, "profile") and getattr(user.profile, "is_chief_editor", False)
    
    def can_publish(self, user):
        return user.is_authenticated and hasattr(user, "profile") and getattr(user.profile, "is_chief_editor", False)
    
    
    def can_edit_banner(self, user):
        """Check if user can edit the story_banner field"""
        return user.is_authenticated and hasattr (user, "profile") and user.profile.is_chief_editor
    
    def can_view(self, user):
        if self.status == 'published':
            return True
        if not user.is_authenticated:
            return False
        if hasattr(user, "profile") and getattr(user.profile, "is_chief_editor", False):
            return True
        return self.author == user
    
    def get_absolute_url(self):
        return reverse('story:blog_detail', kwargs={'slug': self.slug})
    
    @property
    def is_published(self):
        return self.status == 'published'
    
    @property
    def tag_list(self):
        return self.tags.all()

""" ============ Story Chapter =========== """
class StoryChapter(CoreModel):
    story = models.ForeignKey(Story, on_delete=models.CASCADE, related_name='chapters')
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    content = RichTextUploadingField(max_length=1000)
    image = models.ImageField(upload_to='chapter/%y/%m/%d', blank=True, null=True)
    video = models.FileField(upload_to='chapter/%y/%m/%d', blank=True, null=True)
    order = models.PositiveBigIntegerField(default=0)

    class Meta:
        ordering = ['order', 'created_at']
        constraints = [
            models.UniqueConstraint(fields=['story', 'order'], name='unique_story_order')
        ]

    def _make_unique_slug(self):
        base_slug = slugify(self.title) or 'chapter'
        slug = base_slug
        counter = 1
        while StoryChapter.objects.filter(slug=slug).exclude(pk=self.pk).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        return slug

    def clean(self):
        super().clean()
        if not self.slug:
            self.slug = self._make_unique_slug()

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._make_unique_slug()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.story.title} - chapter {self.order}: {self.title}'
""" ============== Story Like ============== """    
class StoryLike(CoreModel):
    story = models.ForeignKey(Story, on_delete=models.CASCADE, related_name='story_like')
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['story', 'user'], name='unique_story_user_like')
        ]

    def __str__(self):
        return f'{self.user.username} like {self.story.title}'

""" ================ Story View ================ """
class StoryView(CoreModel):
    story = models.ForeignKey(Story,on_delete=models.CASCADE, related_name='story_views')  
    user = models.ForeignKey(User, on_delete=models.CASCADE,null=True,blank=True)
    id_adress = models.GenericIPAddressField(null=True,blank=True)
    
    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'View of {self.story.title} at {self.created_at}'


      
""" ============== Story Tags ============= """  
class StoryTag(CoreModel):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True) 
    
    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Story Tags'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name