<?php

namespace App\Http\Controllers;

use App\Models\Fortune;
use App\Models\World;
use Illuminate\Contracts\View\View;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Http\Response;
use Illuminate\Support\Facades\DB;

class BenchController extends Controller
{
    public function text(): Response
    {
        return response('Hello World', 200, ['Content-Type' => 'text/plain; charset=utf-8']);
    }

    public function json(): JsonResponse
    {
        return response()->json(['message' => 'Hello World']);
    }

    public function dbSingle(): JsonResponse
    {
        $world = World::findOrFail(1);

        return response()->json(['id' => $world->id, 'randomNumber' => $world->randomnumber]);
    }

    public function html(): View
    {
        return view('hello', ['name' => 'World']);
    }

    /** One Eloquent query per row. */
    public function queries(Request $request): JsonResponse
    {
        $worlds = [];
        for ($i = self::queryCount($request); $i > 0; $i--) {
            $world = World::findOrFail(random_int(1, 10000));
            $worlds[] = ['id' => $world->id, 'randomNumber' => $world->randomnumber];
        }

        return response()->json($worlds);
    }

    /**
     * Each row read with its own query, given a new random value and saved, in
     * one transaction; the ids are sorted so that concurrent requests lock rows
     * in the same order.
     */
    public function updates(Request $request): JsonResponse
    {
        $ids = [];
        for ($i = self::queryCount($request); $i > 0; $i--) {
            $ids[] = random_int(1, 10000);
        }
        sort($ids);

        $worlds = DB::transaction(function () use ($ids) {
            $worlds = [];
            foreach ($ids as $id) {
                $world = World::findOrFail($id);
                $world->randomnumber = self::newRandomNumber($world->randomnumber);
                $world->save();
                $worlds[] = ['id' => $world->id, 'randomNumber' => $world->randomnumber];
            }

            return $worlds;
        });

        return response()->json($worlds);
    }

    public function fortunes(): View
    {
        $fortunes = Fortune::all()->all();
        $fortunes[] = (new Fortune)->forceFill(['id' => 0, 'message' => 'Additional fortune added at request time.']);
        // strcmp compares the UTF-8 bytes, which orders by code point.
        usort($fortunes, fn (Fortune $a, Fortune $b) => strcmp($a->message, $b->message));

        return view('fortunes', ['fortunes' => $fortunes]);
    }

    /** TechEmpower's rule: an integer clamped to 1..500, anything else is 1. */
    private static function queryCount(Request $request): int
    {
        $value = filter_var($request->query('queries'), FILTER_VALIDATE_INT);

        return $value === false ? 1 : max(1, min(500, $value));
    }

    /** A new value, different from the current one (so that the row changes). */
    private static function newRandomNumber(int $current): int
    {
        do {
            $value = random_int(1, 10000);
        } while ($value === $current);

        return $value;
    }
}
