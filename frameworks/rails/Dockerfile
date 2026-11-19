# syntax=docker/dockerfile:1
# check=error=true;skip=SecretsUsedInArgOrEnv
# (SecretsUsedInArgOrEnv is skipped for the dummy SECRET_KEY_BASE below.)

# The Dockerfile `rails new` generates (Rails 8.1.4.1, PostgreSQL, Thruster),
# with the changes marked "Benchmark:" and explained in README.md.

# Benchmark: resolves Gemfile.lock for the pull request check, which exports
# the `lockfile` stage (see CONTRIBUTING.md). The image below does not use it.
FROM docker.io/library/ruby:4.0.9-slim-trixie AS resolve
WORKDIR /rails
COPY Gemfile ./
RUN bundle lock --add-platform=x86_64-linux

FROM scratch AS lockfile
COPY --from=resolve /rails/Gemfile.lock /

# Make sure RUBY_VERSION matches the Ruby version in .ruby-version
# Benchmark: the image tag is written out (generated: ruby:$RUBY_VERSION-slim).
FROM docker.io/library/ruby:4.0.9-slim-trixie AS base

# Rails app lives here
WORKDIR /rails

# Install base packages
RUN apt-get update -qq && \
    apt-get install --no-install-recommends -y curl libjemalloc2 postgresql-client && \
    ln -s /usr/lib/$(uname -m)-linux-gnu/libjemalloc.so.2 /usr/local/lib/libjemalloc.so && \
    rm -rf /var/lib/apt/lists /var/cache/apt/archives

# Set production environment variables and enable jemalloc for reduced memory usage and latency.
ENV RAILS_ENV="production" \
    BUNDLE_DEPLOYMENT="1" \
    BUNDLE_PATH="/usr/local/bundle" \
    BUNDLE_WITHOUT="development" \
    LD_PRELOAD="/usr/local/lib/libjemalloc.so"

# Throw-away build stage to reduce size of final image
FROM base AS build

# Install packages needed to build gems
RUN apt-get update -qq && \
    apt-get install --no-install-recommends -y build-essential git libpq-dev libyaml-dev pkg-config && \
    rm -rf /var/lib/apt/lists /var/cache/apt/archives

# Install application gems
COPY Gemfile Gemfile.lock ./

RUN bundle install && \
    rm -rf ~/.bundle/ "${BUNDLE_PATH}"/ruby/*/cache "${BUNDLE_PATH}"/ruby/*/bundler/gems/*/.git && \
    # -j 1 disable parallel compilation to avoid a QEMU bug: https://github.com/rails/bootsnap/issues/495
    bundle exec bootsnap precompile -j 1 --gemfile

# Copy application code
COPY . .

# Precompile bootsnap code for faster boot times.
# -j 1 disable parallel compilation to avoid a QEMU bug: https://github.com/rails/bootsnap/issues/495
RUN bundle exec bootsnap precompile -j 1 app/ lib/

# Benchmark: record the resolved versions for the results.
RUN mkdir -p /bench && \
    { echo "ruby $(ruby -e 'print RUBY_VERSION')"; \
      bundle exec ruby -e 'puts %w[rails activerecord actionpack puma pg thruster].map { |n| "#{n} #{Gem.loaded_specs.fetch(n).version}" }'; \
    } > /bench/versions.txt && cat /bench/versions.txt

# Final stage for app image
FROM base

# Run and own only the runtime files as a non-root user for security
RUN groupadd --system --gid 1000 rails && \
    useradd rails --uid 1000 --gid 1000 --create-home --shell /bin/bash
USER 1000:1000

# Copy built artifacts: gems, application
COPY --chown=rails:rails --from=build "${BUNDLE_PATH}" "${BUNDLE_PATH}"
COPY --chown=rails:rails --from=build /rails /rails
COPY --from=build /bench/versions.txt /bench/versions.txt

# Benchmark: the settings below replace what a deployment would provide.
# A fixed dummy secret, the same in every Puma worker: it encrypts the cookie
# session (CSRF token) and signs the session_id cookie of the benchmark's
# test accounts, and protects nothing else.
ENV SECRET_KEY_BASE="benchmark-dummy-secret-key-base-it-protects-nothing-0123456789abcdef0123456789abcdef" \
    RAILS_LOG_LEVEL="warn" \
    LOG_REQUESTS="false"

# Benchmark: no ENTRYPOINT. The generated bin/docker-entrypoint only runs
# `rails db:prepare`, which would create Rails' metadata tables in the
# benchmark database; the schema already exists.

# Start server via Thruster by default, this can be overwritten at runtime
# Benchmark: Thruster listens on $PORT (HTTP_PORT; generated: 80) and starts
# Puma on its default TARGET_PORT 3000; Puma runs BENCH_WORKERS workers.
EXPOSE 8080
CMD ["sh", "-c", "export HTTP_PORT=\"${PORT:-8080}\" WEB_CONCURRENCY=\"${WEB_CONCURRENCY:-${BENCH_WORKERS:-2}}\"; exec ./bin/thrust ./bin/rails server"]
