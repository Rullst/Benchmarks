<?php

namespace App\Models;

use Illuminate\Foundation\Auth\User as Authenticatable;

/**
 * The skeleton's User model on the shared `users` table
 * (bench/db/phase2.sql), which has no timestamps or remember token and keeps
 * the bcrypt hash in `password_bcrypt`.
 */
class User extends Authenticatable
{
    public $timestamps = false;

    protected $hidden = ['password_bcrypt', 'password_argon2id'];

    public function getAuthPasswordName()
    {
        return 'password_bcrypt';
    }

    /**
     * The stored hash has bcrypt's "$2b$" prefix; PHP's password API names
     * the same algorithm "$2y$" and Laravel's bcrypt hasher refuses other
     * prefixes (docs/v3-spec.md, section 9).
     */
    public function getAuthPassword()
    {
        return '$2y$'.substr($this->password_bcrypt, 4);
    }

    public function getRememberTokenName()
    {
        return '';
    }
}
