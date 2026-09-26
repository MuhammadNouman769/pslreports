from django.urls import path
from . import views

app_name = 'story'

urlpatterns = [
    path('', views.story_list, name='stories'),
    path('<slug:slug>/', views.blog_detail, name='blog_detail'),
]