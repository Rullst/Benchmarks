<?php

use App\Http\Controllers\BenchController;
use App\Http\Controllers\FormController;
use App\Http\Controllers\SessionController;
use Illuminate\Support\Facades\Route;

// The HTML page uses the default "web" middleware group (cookies, session,
// CSRF protection).
Route::get('/html', [BenchController::class, 'html']);

// Phase 2: the browser-facing routes, in the same group.
Route::get('/form', [FormController::class, 'create']);
Route::post('/form', [FormController::class, 'store']);
Route::get('/login', [SessionController::class, 'create'])->name('login');
Route::post('/login', [SessionController::class, 'store']);
Route::get('/me', [SessionController::class, 'me'])->middleware('auth');
