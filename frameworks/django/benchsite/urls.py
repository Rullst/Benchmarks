"""
URL configuration for benchsite project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
"""
from django.urls import path

from world import views

urlpatterns = [
    path('text', views.text),
    path('json', views.json),
    path('db-single', views.db_single),
    path('html', views.html),
]
