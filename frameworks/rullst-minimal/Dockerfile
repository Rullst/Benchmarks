FROM rust:1.99.1-slim-bookworm AS build
# Empty: build the version pinned in Cargo.toml and Cargo.lock. Otherwise the
# exact pins are rewritten to this published version and Cargo re-resolves
# only what that change requires.
ARG RULLST_VERSION=
WORKDIR /src
COPY Cargo.toml Cargo.lock ./
COPY src ./src
RUN set -eu; \
    case "$RULLST_VERSION" in *[!0-9A-Za-z.+-]*) echo "invalid RULLST_VERSION" >&2; exit 1;; esac; \
    if [ -n "$RULLST_VERSION" ] && ! grep -q "^rullst = { version = \"=$RULLST_VERSION\"" Cargo.toml; then \
      sed -i -E "s/^(rullst(-orm)? = \{ version = \")=[^\"]+/\1=$RULLST_VERSION/" Cargo.toml; \
      cargo build --release; \
    else \
      cargo build --release --locked; \
    fi
# Record the resolved versions of the main crates for the results, and where
# Cargo took the rullst crate from (`rullst-source`: crates.io or a git
# revision), which the results show next to the version.
RUN mkdir /out && cp target/release/rullst-minimal-bench /out/server \
    && awk -F' = ' '/^name = /{gsub(/"/,"",$2); n=$2} /^version = /{gsub(/"/,"",$2); print n, $2} /^source = /{gsub(/"/,"",$2); if (n == "rullst") print "rullst-source", $2}' Cargo.lock \
       | grep -E '^(rullst|rullst-source|rullst-core|rullst-orm|rullst-auth|axum|hyper|tokio|sqlx|validator) ' > /out/versions.txt

# `docker build --target lockfile --output <dir>` writes Cargo.lock re-resolved
# for Cargo.toml (Rust is not needed locally; CI uploads it): only what a
# change to Cargo.toml requires is re-resolved, for example after the Rullst
# pin moves to a new release. The image itself uses the committed file.
FROM rust:1.99.1-slim-bookworm AS resolve
WORKDIR /src
COPY Cargo.toml Cargo.lock ./
COPY src ./src
RUN cargo metadata --format-version 1 > /dev/null

FROM scratch AS lockfile
COPY --from=resolve /src/Cargo.lock /

FROM gcr.io/distroless/cc-debian12:nonroot@sha256:9dac0a79194e45a7da0158a9c6da57b217585af0786db3845d1f0ec1a0dd182f
COPY --from=build /out/server /app/server
COPY --from=build /out/versions.txt /bench/versions.txt
# As in the Dockerfile `cargo rullst deploy` generates.
ENV RULLST_ENV=production
ENV HOST=0.0.0.0
EXPOSE 8080
CMD ["/app/server"]
