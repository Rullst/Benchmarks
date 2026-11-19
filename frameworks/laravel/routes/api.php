<?php

use App\Http\Controllers\BenchController;
use App\Http\Controllers\WorldController;
use Illuminate\Support\Facades\Route;

// The stateless endpoints use the "api" middleware group.
Route::get('/text', [BenchController::class, 'text']);
Route::get('/json', [BenchController::class, 'json']);
Route::get('/db-single', [BenchController::class, 'dbSingle']);

// Phase 1: the TechEmpower-style database endpoints.
Route::get('/queries', [BenchController::class, 'queries']);
Route::get('/updates', [BenchController::class, 'updates']);
Route::get('/fortunes', [BenchController::class, 'fortunes']);

// Phase 2: a non-integer id matches no route (404). PUT /world/{id} is a
// public JSON API call: the api group has no CSRF check.
Route::get('/world/{id}', [WorldController::class, 'show'])->whereNumber('id');
Route::put('/world/{id}', [WorldController::class, 'update'])->whereNumber('id');
Route::get('/worlds', [WorldController::class, 'index']);
