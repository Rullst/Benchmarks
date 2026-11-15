<?php

use App\Http\Controllers\BenchController;
use Illuminate\Support\Facades\Route;

// The HTML page uses the default "web" middleware group (cookies, session,
// CSRF protection).
Route::get('/html', [BenchController::class, 'html']);
