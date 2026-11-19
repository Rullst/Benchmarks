<?php

use Illuminate\Foundation\Application;
use Illuminate\Foundation\Configuration\Exceptions;
use Illuminate\Foundation\Configuration\Middleware;
use Illuminate\Http\Request;

return Application::configure(basePath: dirname(__DIR__))
    ->withRouting(
        web: __DIR__.'/../routes/web.php',
        // Benchmark: the stateless API routes (routes/api.php), served without
        // the default /api prefix so that the endpoints keep the suite's paths.
        api: __DIR__.'/../routes/api.php',
        apiPrefix: '',
        commands: __DIR__.'/../routes/console.php',
        health: '/up',
    )
    ->withMiddleware(function (Middleware $middleware): void {
        //
    })
    ->withExceptions(function (Exceptions $exceptions): void {
        // Benchmark: the api group is served without the /api prefix, so its
        // routes are recognised by their middleware group rather than by
        // is('api/*'): their errors (validation 422, 404) are JSON.
        $exceptions->shouldRenderJsonWhen(
            fn (Request $request) => $request->expectsJson()
                || in_array('api', $request->route()?->middleware() ?? [], true),
        );
    })->create();
