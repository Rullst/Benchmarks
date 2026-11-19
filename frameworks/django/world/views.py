import json as jsonlib
import random
from operator import attrgetter

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .forms import GreetingForm, WorldsForm, WorldUpdateForm
from .models import Fortune, World


def text(request):
    return HttpResponse('Hello World', content_type='text/plain; charset=utf-8')


def json(request):
    return JsonResponse({'message': 'Hello World'})


def db_single(request):
    world = World.objects.get(pk=1)
    return JsonResponse({'id': world.id, 'randomNumber': world.randomnumber})


def html(request):
    return render(request, 'hello.html', {'name': 'World'})


# ---------------------------------------------------------------- phase 1

def _query_count(request):
    """TechEmpower's rule: an integer clamped to 1..500, anything else is 1."""
    try:
        return min(max(int(request.GET.get('queries', '')), 1), 500)
    except ValueError:
        return 1


def _random_id():
    return random.randint(1, 10000)


def queries(request):
    """One ORM query per row."""
    worlds = [World.objects.get(pk=_random_id()) for _ in range(_query_count(request))]
    return JsonResponse([{'id': w.id, 'randomNumber': w.randomnumber} for w in worlds], safe=False)


def updates(request):
    """Each row read with its own query, given a new value and saved, in one
    transaction; the ids are sorted so that concurrent requests lock rows in
    the same order."""
    ids = sorted(_random_id() for _ in range(_query_count(request)))
    rows = []
    with transaction.atomic():
        for ident in ids:
            world = World.objects.get(pk=ident)
            value = _random_id()
            while value == world.randomnumber:
                value = _random_id()
            world.randomnumber = value
            world.save(update_fields=['randomnumber'])
            rows.append({'id': world.id, 'randomNumber': world.randomnumber})
    return JsonResponse(rows, safe=False)


def fortunes(request):
    rows = list(Fortune.objects.all())
    rows.append(Fortune(id=0, message='Additional fortune added at request time.'))
    rows.sort(key=attrgetter('message'))
    return render(request, 'fortunes.html', {'fortunes': rows})


# ---------------------------------------------------------------- phase 2

def _world_json(world):
    return JsonResponse({'id': world.id, 'randomNumber': world.randomnumber})


# PUT /world/{id} is a public JSON API call, sent without cookies:
# csrf_exempt is Django's documented exemption from CsrfViewMiddleware.
@csrf_exempt
@require_http_methods(['GET', 'PUT'])
def world(request, id):
    if request.method == 'PUT':
        return _update_world(request, id)
    world = World.objects.filter(pk=id).first()
    if world is None:
        return JsonResponse({'error': 'not found'}, status=404)
    return _world_json(world)


def _update_world(request, id):
    """The body is validated before the row is loaded, so a refused request
    writes nothing; then the usual get, assign and save."""
    try:
        body = jsonlib.loads(request.body)
    except ValueError:
        return JsonResponse({'error': 'malformed JSON'}, status=400)
    form = WorldUpdateForm(body if isinstance(body, dict) else {})
    if not form.is_valid():
        return JsonResponse({'errors': form.errors.get_json_data()}, status=422)
    world = World.objects.filter(pk=id).first()
    if world is None:
        return JsonResponse({'error': 'not found'}, status=404)
    world.randomnumber = form.cleaned_data['randomNumber']
    world.save(update_fields=['randomnumber'])
    return _world_json(world)


def worlds(request):
    """One query: the filter, ORDER BY, LIMIT and OFFSET run in PostgreSQL."""
    form = WorldsForm(request.GET)
    if not form.is_valid():
        return JsonResponse({'errors': form.errors.get_json_data()}, status=422)
    query = form.cleaned_data
    offset = (query['page'] - 1) * query['limit']
    rows = World.objects.filter(id__gte=query['min'], id__lte=query['max']).order_by('id')[
        offset:offset + query['limit']]
    return JsonResponse([{'id': w.id, 'randomNumber': w.randomnumber} for w in rows], safe=False)


@require_http_methods(['GET', 'POST'])
def form_page(request):
    """GET /form and POST /form; CsrfViewMiddleware checks the post first (403)."""
    if request.method != 'POST':
        return render(request, 'form.html', {'form': GreetingForm()})
    form = GreetingForm(request.POST)
    if not form.is_valid():
        return render(request, 'form.html', {'form': form}, status=422)
    return render(request, 'form_result.html', form.cleaned_data)


@login_required
def me(request):
    """request.user comes from AuthenticationMiddleware: the session's user id,
    then the user's row (ModelBackend.get_user), on every request."""
    user = request.user
    return JsonResponse({'id': user.id, 'username': user.username, 'displayName': user.display_name})
