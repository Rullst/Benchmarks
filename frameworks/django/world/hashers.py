from django.contrib.auth.hashers import BCryptPasswordHasher


class BCryptCost10PasswordHasher(BCryptPasswordHasher):
    """Django's BCryptPasswordHasher with the work factor of the stored hashes.

    bench/db/phase2.sql hashes with cost 10; with Django's default (12) every
    login would rehash the password and write it to `users`. Subclassing to set
    `rounds` is how Django's password documentation changes the work factor.
    """

    rounds = 10
