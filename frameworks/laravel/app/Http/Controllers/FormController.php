<?php

namespace App\Http\Controllers;

use Illuminate\Contracts\View\View;
use Illuminate\Http\Request;

/**
 * GET /form and POST /form (docs/v3-spec.md, section 4), in the web
 * group: PreventRequestForgery checks the request first (419 when forged),
 * then `$request->validate` checks the fields (an invalid post is redirected
 * back with the errors, 302).
 */
class FormController extends Controller
{
    public function create(): View
    {
        return view('form');
    }

    public function store(Request $request): View
    {
        $fields = $request->validate([
            'name' => ['required', 'string', 'between:1,64'],
            'randomNumber' => ['required', 'integer', 'between:1,10000'],
        ]);

        return view('form_result', ['name' => $fields['name'], 'randomNumber' => (int) $fields['randomNumber']]);
    }
}
