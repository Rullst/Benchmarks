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
# Record the resolved versions of the main crates for the results.
RUN mkdir /out && cp target/release/rullst-bench /out/server \
    && awk -F' = ' '/^name = /{gsub(/"/,"",$2); n=$2} /^version = /{gsub(/"/,"",$2); print n, $2}' Cargo.lock \
       | grep -E '^(rullst|rullst-core|rullst-orm|axum|hyper|tokio|sqlx) ' > /out/versions.txt

FROM gcr.io/distroless/cc-debian12:nonroot@sha256:9dac0a79194e45a7da0158a9c6da57b217585af0786db3845d1f0ec1a0dd182f
COPY --from=build /out/server /app/server
COPY --from=build /out/versions.txt /bench/versions.txt
# As in the Dockerfile `cargo rullst deploy` generates.
ENV RULLST_ENV=production
ENV HOST=0.0.0.0
EXPOSE 8080
CMD ["/app/server"]
