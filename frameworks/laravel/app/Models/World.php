<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

/**
 * The benchmark's existing `world` table.
 */
class World extends Model
{
    protected $table = 'world';

    public $timestamps = false;

    protected function casts(): array
    {
        return [
            'randomnumber' => 'integer',
        ];
    }
}
