<?php

namespace App\Http\Controllers;

use App\Models\World;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Validation\ValidationException;

/**
 * GET /world/{id}, GET /worlds and PUT /world/{id} (docs/v3-spec.md,
 * section 3). whereNumber('id') answers 404 for a non-integer id; failed
 * validation is answered 422 (bootstrap/app.php renders the api group's
 * exceptions as JSON).
 */
class WorldController extends Controller
{
    public function show(int $id): JsonResponse
    {
        $world = World::find($id);
        if ($world === null) {
            abort(404);
        }

        return response()->json(['id' => $world->id, 'randomNumber' => $world->randomnumber]);
    }

    /** One query: the filter, ORDER BY, LIMIT and OFFSET run in PostgreSQL. */
    public function index(Request $request): JsonResponse
    {
        $query = $request->validate([
            'min' => ['sometimes', 'integer', 'between:1,10000'],
            'max' => ['sometimes', 'integer', 'between:1,10000'],
            'limit' => ['sometimes', 'integer', 'between:1,100'],
            'page' => ['sometimes', 'integer', 'between:1,1000'],
        ]);
        $min = (int) ($query['min'] ?? 1);
        $max = (int) ($query['max'] ?? 10000);
        $limit = (int) ($query['limit'] ?? 20);
        $page = (int) ($query['page'] ?? 1);
        if ($min > $max) {
            throw ValidationException::withMessages(['min' => 'The min field must not be greater than max.']);
        }

        $worlds = World::query()
            ->whereBetween('id', [$min, $max])
            ->orderBy('id')
            ->limit($limit)
            ->offset(($page - 1) * $limit)
            ->get(['id', 'randomnumber']);

        return response()->json($worlds->map(fn (World $world) => [
            'id' => $world->id,
            'randomNumber' => $world->randomnumber,
        ]));
    }

    /**
     * The body is validated before the row is loaded, so a refused request
     * writes nothing; then the usual find, assign and save. `integer:strict`
     * refuses a JSON string such as "5".
     */
    public function update(Request $request, int $id): JsonResponse
    {
        $body = $request->validate([
            'randomNumber' => ['required', 'integer:strict', 'between:1,10000'],
        ]);

        $world = World::find($id);
        if ($world === null) {
            abort(404);
        }
        $world->randomnumber = $body['randomNumber'];
        $world->save();

        return response()->json(['id' => $world->id, 'randomNumber' => $world->randomnumber]);
    }
}
