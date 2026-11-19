# The Dockerfile `mix phx.gen.release --docker` generates (Phoenix 1.8.16),
# with the changes marked "Benchmark:" and explained in README.md.
#
# This file is based on these images:
#
#   - https://hub.docker.com/r/hexpm/elixir/tags - for the builder image
#     E.g.: docker.io/hexpm/elixir:1.20.5-erlang-29.1.2-debian-trixie-20261104-slim
#   - https://hub.docker.com/_/debian/tags?name=trixie-20261104-slim - for the runner image
#     E.g.: docker.io/debian:trixie-20261104-slim
#
# We suggest using the same Debian version for both the builder and runner images.
#
# Benchmark: the image references are written out in the FROM lines
# (generated: ARG ELIXIR_VERSION=1.20.5, OTP_VERSION=29.1.2,
# DEBIAN_VERSION=trixie-20261104-slim, BUILDER_IMAGE and RUNNER_IMAGE), so
# the harness can record their digests.

# Benchmark: resolves mix.lock for the pull request check, which exports the
# `lockfile` stage (see CONTRIBUTING.md). The image below does not use it.
FROM docker.io/hexpm/elixir:1.20.5-erlang-29.1.2-debian-trixie-20261104-slim AS resolve
WORKDIR /app
RUN mix local.hex --force \
  && mix local.rebar --force
COPY mix.exs ./
RUN mix deps.get

FROM scratch AS lockfile
COPY --from=resolve /app/mix.lock /

FROM docker.io/hexpm/elixir:1.20.5-erlang-29.1.2-debian-trixie-20261104-slim AS builder

# install build dependencies
RUN apt-get update \
  && apt-get install -y --no-install-recommends build-essential git \
  && rm -rf /var/lib/apt/lists/*

# prepare build dir
WORKDIR /app

# install hex + rebar
RUN mix local.hex --force \
  && mix local.rebar --force

# set build ENV
ENV MIX_ENV="prod"

# install mix dependencies
COPY mix.exs mix.lock ./
RUN mix deps.get --only $MIX_ENV
RUN mkdir config

# copy compile-time config files before we compile dependencies
# to ensure any relevant config change will trigger the dependencies
# to be re-compiled.
COPY config/config.exs config/${MIX_ENV}.exs config/
RUN mix deps.compile

COPY priv priv

COPY lib lib

# Compile the release
RUN mix compile

# Changes to config/runtime.exs don't require recompiling the code
COPY config/runtime.exs config/

COPY rel rel
RUN mix release

# Benchmark: record the resolved versions for the results.
RUN mkdir /out \
  && { echo "elixir $(elixir --short-version)"; \
       erl -noshell -eval '{ok, V} = file:read_file(filename:join([code:root_dir(), "releases", erlang:system_info(otp_release), "OTP_VERSION"])), io:format("otp ~s~n", [string:trim(V)]), halt().'; \
       mix deps | sed -nE 's/^\* ([a-z_]+) ([0-9][^ ]*) .*/\1 \2/p' \
         | grep -E '^(phoenix|phoenix_live_view|phoenix_html|bandit|thousand_island|plug|ecto|ecto_sql|postgrex|db_connection) '; \
     } > /out/versions.txt \
  && cat /out/versions.txt

# start a new build stage so that the final image will only contain
# the compiled release and other runtime necessities
FROM docker.io/debian:trixie-20261104-slim AS final

RUN apt-get update \
  && apt-get install -y --no-install-recommends libstdc++6 openssl libncurses6 locales ca-certificates \
  && rm -rf /var/lib/apt/lists/*

# Set the locale
RUN sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen \
  && locale-gen

ENV LANG=en_US.UTF-8
ENV LANGUAGE=en_US:en
ENV LC_ALL=en_US.UTF-8

WORKDIR "/app"
RUN chown nobody /app

# set runner ENV
ENV MIX_ENV="prod"

# Only copy the final release from the build stage
COPY --from=builder --chown=nobody:root /app/_build/${MIX_ENV}/rel/bench ./
COPY --from=builder /out/versions.txt /bench/versions.txt

# Benchmark: a fixed dummy secret (the generated release reads it from the
# deployment's environment). It signs the session cookie of the benchmark's
# test accounts and protects nothing else.
ENV SECRET_KEY_BASE="benchmark-dummy-secret-key-base-it-protects-nothing-0123456789abcdef0123456789abcdef"

USER nobody

# If using an environment that doesn't automatically reap zombie processes, it is
# advised to add an init process such as tini via `apt-get install`
# above and adding an entrypoint. See https://github.com/krallin/tini for details
# ENTRYPOINT ["/tini", "--"]

EXPOSE 8080
CMD ["/app/bin/server"]
