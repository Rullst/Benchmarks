FROM rust:1.99.1-slim-bookworm AS build
WORKDIR /src
COPY Cargo.toml Cargo.lock ./
COPY src ./src
RUN cargo build --release --locked
# Record the resolved versions of the main crates for the results.
RUN mkdir /out && cp target/release/topcoat-bench /out/server \
    && awk -F' = ' '/^name = /{gsub(/"/,"",$2); n=$2} /^version = /{gsub(/"/,"",$2); print n, $2}' Cargo.lock \
       | grep -E '^(topcoat|topcoat-router|topcoat-view|topcoat-session|topcoat-cookie|toasty|toasty-driver-postgresql|tokio|hyper|argon2) ' > /out/versions.txt

FROM gcr.io/distroless/cc-debian12:nonroot@sha256:9dac0a79194e45a7da0158a9c6da57b217585af0786db3845d1f0ec1a0dd182f
COPY --from=build /out/server /app/server
COPY --from=build /out/versions.txt /bench/versions.txt
# `topcoat::start` reads HOST and PORT.
ENV HOST=0.0.0.0
EXPOSE 8080
CMD ["/app/server"]
