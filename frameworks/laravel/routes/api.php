<?php

use App\Http\Controllers\BenchController;
use Illuminate\Support\Facades\Route;

// The stateless endpoints use the "api" middleware group.
Route::get('/text', [BenchController::class, 'text']);
Route::get('/json', [BenchController::class, 'json']);
Route::get('/db-single', [BenchController::class, 'dbSingle']);
