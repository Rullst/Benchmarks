FROM rust:1.94-bookworm AS builder
WORKDIR /usr/src/app
COPY . .
RUN cargo build --release

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y libpq-dev openssl ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=builder /usr/src/app/target/release/rullst-bench /usr/local/bin/rullst-bench
ENV DATABASE_URL=postgres://postgres:postgres@db:5432/bench
EXPOSE 3000
CMD ["rullst-bench"]
