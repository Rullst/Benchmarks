#!/bin/sh
# Runs the deployment step from Laravel's documentation (php artisan optimize)
# and starts PHP-FPM and Nginx.
set -eu

# Laravel's pgsql connection reads DB_URL; the harness sets DATABASE_URL.
export DB_URL="${DB_URL:-${DATABASE_URL:-}}"

# Cache the configuration, events, routes and views. This runs at start-up,
# not in the image build, because the cached configuration keeps the
# environment it was created in (DB_URL, APP_KEY, ...).
php artisan optimize
chown -R www-data:www-data storage bootstrap/cache

sed "s/@PORT@/${PORT:-8080}/" /etc/nginx/laravel-site.conf > /etc/nginx/sites-enabled/laravel
# One Nginx worker per vCPU of the container. Debian's "worker_processes auto"
# counts the host's online CPUs, not the CPUs the container may use.
sed -i "s/^worker_processes .*;/worker_processes ${BENCH_WORKERS:-auto};/" /etc/nginx/nginx.conf

php-fpm --daemonize
exec nginx -g 'daemon off;'
