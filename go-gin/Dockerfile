FROM golang:alpine AS builder

WORKDIR /app

COPY . .
RUN go mod tidy
RUN go mod download

# Build with optimization
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-w -s" -o benchmark-go-gin main.go

FROM alpine:latest

WORKDIR /app
COPY --from=builder /app/benchmark-go-gin .

EXPOSE 8080

CMD ["./benchmark-go-gin"]
