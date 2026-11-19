"""
URL configuration for benchsite project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
"""
from django.contrib.auth import views as auth_views
from django.urls import path

from world import views

urlpatterns = [
    path('text', views.text),
    path('json', views.json),
    path('db-single', views.db_single),
    path('html', views.html),
    # Phase 1.
    path('queries', views.queries),
    path('updates', views.updates),
    path('fortunes', views.fortunes),
    # Phase 2. The <int:id> converter matches digits only: 404 otherwise.
    path('world/<int:id>', views.world),
    path('worlds', views.worlds),
    path('form', views.form_page),
    path('login', auth_views.LoginView.as_view(template_name='login.html')),
    path('me', views.me),
]
