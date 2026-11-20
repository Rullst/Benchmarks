<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

/**
 * The benchmark's existing `fortune` table.
 */
class Fortune extends Model
{
    protected $table = 'fortune';

    public $timestamps = false;
}
