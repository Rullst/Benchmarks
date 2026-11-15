<?php

namespace App\Http\Controllers;

use App\Models\World;
use Illuminate\Contracts\View\View;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Response;

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
}
