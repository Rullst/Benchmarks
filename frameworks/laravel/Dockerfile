# Laravel does not generate a Dockerfile. This image serves the application
# the way Laravel's deployment documentation describes it
# (https://laravel.com/docs/13.x/deployment): Nginx with the documented server
# block in front of PHP-FPM, Composer's production install and
# `php artisan optimize`. Details and changes are in README.md.

# Resolves composer.lock for the pull request check, which exports the
# `lockfile` stage (see CONTRIBUTING.md). The image below does not use it.
FROM php:8.5.12-cli-trixie AS resolve
COPY --from=composer:2.11.2 /usr/bin/composer /usr/bin/composer
ENV COMPOSER_ALLOW_SUPERUSER=1
WORKDIR /app
COPY composer.json ./
RUN composer update --no-install --no-interaction --no-scripts --no-plugins

FROM scratch AS lockfile
COPY --from=resolve /app/composer.lock /

FROM php:8.5.12-cli-trixie AS build
RUN apt-get update \
    && apt-get install -y --no-install-recommends git unzip \
    && rm -rf /var/lib/apt/lists/*
COPY --from=composer:2.11.2 /usr/bin/composer /usr/bin/composer
ENV COMPOSER_ALLOW_SUPERUSER=1
WORKDIR /app
COPY composer.json composer.lock ./
RUN composer install --no-dev --no-interaction --no-scripts --no-autoloader --prefer-dist
COPY . .
# The optimized autoloader; its post-autoload-dump scripts run Laravel's
# package discovery.
RUN mkdir -p storage/app/private storage/app/public storage/framework/cache/data \
        storage/framework/sessions storage/framework/views storage/logs \
    && composer dump-autoload --no-dev --optimize --no-interaction
# Record the resolved versions for the results.
RUN mkdir /out \
    && php -r '$lock = json_decode(file_get_contents("composer.lock"), true); foreach ($lock["packages"] as $p) { if (in_array($p["name"], ["laravel/framework", "symfony/http-foundation", "symfony/http-kernel"], true)) { echo $p["name"], " ", ltrim($p["version"], "v"), "\n"; } }' \
       > /out/versions.txt \
    && cat /out/versions.txt

FROM php:8.5.12-fpm-trixie
# The pdo_pgsql extension and Debian's Nginx package.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq-dev nginx \
    && docker-php-ext-install -j"$(nproc)" pdo_pgsql \
    && rm -rf /var/lib/apt/lists/*
# The production php.ini, as the image's documentation recommends. OPcache is
# part of PHP 8.5 and on by default for PHP-FPM; the check fails the build if
# it is not loaded.
RUN mv "$PHP_INI_DIR/php.ini-production" "$PHP_INI_DIR/php.ini" \
    && php -r 'exit(function_exists("opcache_get_status") ? 0 : 1);'
# Logging off: the image's docker.conf sends PHP-FPM's access log to stderr;
# remove that line. Errors from Nginx go to stderr.
RUN sed -i '/^access\.log/d' /usr/local/etc/php-fpm.d/docker.conf \
    && mkdir -p /run/php \
    && rm -f /etc/nginx/sites-enabled/default \
    && ln -sf /dev/stderr /var/log/nginx/error.log
COPY docker/php-fpm-pool.conf /usr/local/etc/php-fpm.d/zzz-bench.conf
COPY docker/opcache.ini "$PHP_INI_DIR/conf.d/zz-opcache.ini"
COPY docker/nginx-site.conf /etc/nginx/laravel-site.conf
COPY docker/start.sh /usr/local/bin/start-laravel
WORKDIR /var/www/html
COPY --from=build --chown=www-data:www-data /app ./
COPY --from=build /out/versions.txt /tmp/versions.txt
RUN mkdir /bench \
    && { cat /tmp/versions.txt; \
         echo "php $(php -r 'echo PHP_VERSION;')"; \
         nginx -v 2>&1 | sed -n 's|^nginx version: nginx/|nginx |p'; \
       } > /bench/versions.txt \
    && rm /tmp/versions.txt && cat /bench/versions.txt
# Production settings, read by `php artisan optimize` at start-up. APP_KEY is a
# fixed dummy key (every PHP-FPM process encrypts the session and CSRF
# cookies with it); it protects only the benchmark's test accounts.
# BCRYPT_ROUNDS is the cost of the stored hashes (bench/db/phase2.sql: 10), so
# Laravel's rehash-on-login does not rewrite users.password_bcrypt.
# The session driver is set in config/session.php (cookie; see README.md).
ENV APP_ENV=production \
    APP_DEBUG=false \
    APP_KEY=base64:YmVuY2htYXJrLWR1bW15LWtleS1wcm90ZWN0cy1ubyE= \
    DB_CONNECTION=pgsql \
    BCRYPT_ROUNDS=10 \
    LOG_CHANNEL=stderr \
    LOG_LEVEL=warning
EXPOSE 8080
CMD ["start-laravel"]
