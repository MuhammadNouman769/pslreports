from django.contrib import admin
from django import forms
from django.forms.models import BaseInlineFormSet
from ckeditor_uploader.widgets import CKEditorUploadingWidget
from .models import Story, StoryChapter, StoryTag

# -------------------------
# 1️ StoryChapter form with CKEditor
# -------------------------
class StoryChapterForm(forms.ModelForm):
    content = forms.CharField(widget=CKEditorUploadingWidget())

    class Meta:
        model = StoryChapter
        fields = ['title', 'slug', 'content', 'order', 'image', 'video']

# -------------------------
# 2️ Custom Formset for chapter validation
# -------------------------
class ConditionalChapterFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        count = 0
        for form in self.forms:
            if not form.cleaned_data.get("DELETE", False) and form.cleaned_data:
                count += 1
        
        story = self.instance
        story_status = getattr(story, "status", None)
        if story_status in ["submitted", "published"] and count < 1:
            raise forms.ValidationError(
                "At least one chapter is required before submitting or publishing this story."
            )

# -------------------------
# 3️ Inline admin for StoryChapter
# -------------------------
class StoryChapterInline(admin.StackedInline):
    model = StoryChapter
    form = StoryChapterForm
    formset = ConditionalChapterFormSet
    extra = 1
    can_delete = True
    ordering = ['order']
    show_change_link = True  # link to edit chapter separately if needed

# -------------------------
# 4️ Story admin
# -------------------------
@admin.register(Story)
class StoryAdmin(admin.ModelAdmin):

    list_display = ('title', 'author', 'status', 'post_type', 'published_at', 'views_count', 'likes_count')
    list_filter = ('status', 'post_type', 'author', 'published_at')
    search_fields = ('title', 'content', 'author__username')
    prepopulated_fields = {"slug": ("title",)}
    inlines = [StoryChapterInline]  # Add inline chapters
    readonly_fields = ('views_count', 'likes_count')
    ordering = ('-published_at',)

# -------------------------
# 5️StoryTag admin
# -------------------------
@admin.register(StoryTag)
class StoryTagAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {"slug": ("name",)}
    ordering = ('name',)
