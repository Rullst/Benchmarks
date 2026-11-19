from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models


class World(models.Model):
    """The benchmark's existing `world` table (not managed by migrations)."""

    id = models.IntegerField(primary_key=True)
    randomnumber = models.IntegerField()

    class Meta:
        db_table = 'world'
        managed = False


class Fortune(models.Model):
    """The benchmark's existing `fortune` table (not managed by migrations)."""

    id = models.IntegerField(primary_key=True)
    message = models.CharField(max_length=2048)

    class Meta:
        db_table = 'fortune'
        managed = False


class UserManager(BaseUserManager):
    pass


class User(AbstractBaseUser):
    """The custom user model (AUTH_USER_MODEL) on the shared `users` table.

    bench/db/phase2.sql keeps a bcrypt hash in `password_bcrypt`; Django's
    hashers read "<algorithm>$<hash>", so `password` is that column with the
    "bcrypt$" prefix of BCryptPasswordHasher. The table has no `last_login`
    column, so the field is removed (Django then does not record logins).
    """

    id = models.IntegerField(primary_key=True)
    username = models.CharField(max_length=64, unique=True)
    display_name = models.CharField(max_length=128)
    password_bcrypt = models.CharField(max_length=60)
    last_login = None

    USERNAME_FIELD = 'username'

    objects = UserManager()

    class Meta:
        db_table = 'users'
        managed = False

    @property
    def password(self):
        return 'bcrypt$' + self.password_bcrypt

    @password.setter
    def password(self, encoded):
        self.password_bcrypt = encoded.removeprefix('bcrypt$')
