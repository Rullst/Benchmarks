FROM golang:alpine AS builder

WORKDIR /app

COPY . .
RUN go mod tidy
RUN go mod download

# Build with optimization
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-w -s" -o benchmark-go-fiber main.go

FROM alpine:latest

WORKDIR /app
COPY --from=builder /app/benchmark-go-fiber .

EXPOSE 3000

CMD ["./benchmark-go-fiber"]
