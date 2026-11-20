FROM rust:1.99.1-slim-bookworm AS build
WORKDIR /src
COPY Cargo.toml Cargo.lock ./
COPY src ./src
RUN cargo build --release --locked
# Record the resolved versions of the main crates for the results.
RUN mkdir /out && cp target/release/loco_bench-cli /out/server \
    && awk -F' = ' '/^name = /{gsub(/"/,"",$2); n=$2} /^version = /{gsub(/"/,"",$2); print n, $2}' Cargo.lock \
       | grep -E '^(loco-rs|sea-orm|sqlx|axum|axum_csrf|validator|tera|tokio|hyper) ' > /out/versions.txt

FROM gcr.io/distroless/cc-debian12:nonroot@sha256:9dac0a79194e45a7da0158a9c6da57b217585af0786db3845d1f0ec1a0dd182f
WORKDIR /app
COPY --from=build /out/server /app/loco_bench-cli
COPY --from=build /out/versions.txt /bench/versions.txt
COPY config /app/config
COPY assets /app/assets
# Production environment; the application logger at warn (the request logger
# middleware is off in config/production.yaml).
ENV LOCO_ENV=production
ENV LOG_LEVEL=warn
EXPOSE 8080
ENTRYPOINT ["/app/loco_bench-cli"]
CMD ["start"]
