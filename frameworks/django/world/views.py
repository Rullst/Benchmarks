from django.http import HttpResponse, JsonResponse
from django.shortcuts import render

from .models import World


def text(request):
    return HttpResponse('Hello World', content_type='text/plain; charset=utf-8')


def json(request):
    return JsonResponse({'message': 'Hello World'})


def db_single(request):
    world = World.objects.get(pk=1)
    return JsonResponse({'id': world.id, 'randomNumber': world.randomnumber})


def html(request):
    return render(request, 'hello.html', {'name': 'World'})
