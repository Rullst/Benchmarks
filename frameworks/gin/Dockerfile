FROM golang:1.27.4-trixie@sha256:b54b2639de8c1bfe538ec5ffc45f29b1932235ac5f6d63c059853646677112d9 AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download && go mod verify
COPY *.go ./
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/server .
# Record the resolved versions of the main modules for the results.
RUN { echo "go $(go env GOVERSION | sed 's/^go//')"; \
      go list -m -f '{{.Path}} {{.Version}}' github.com/gin-gonic/gin github.com/gin-contrib/sessions gorm.io/gorm gorm.io/driver/postgres github.com/jackc/pgx/v5 \
        | sed 's/ v/ /'; } > /out/versions.txt && cat /out/versions.txt

# `docker build --target lockfile --output <dir>` resolves go.mod and go.sum
# from scratch (Go is not needed locally); the image itself uses the
# committed files.
FROM golang:1.27.4-trixie@sha256:b54b2639de8c1bfe538ec5ffc45f29b1932235ac5f6d63c059853646677112d9 AS resolve
WORKDIR /src
COPY go.mod *.go ./
RUN go mod tidy

FROM scratch AS lockfile
COPY --from=resolve /src/go.mod /src/go.sum /

FROM gcr.io/distroless/static-debian13:nonroot@sha256:aafe993665bf6200db38a02c11a9351e782a84b6a45e7f33b6695638c88e3931
WORKDIR /app
COPY --from=build /out/server /app/server
COPY templates /app/templates
COPY --from=build /out/versions.txt /bench/versions.txt
# Release mode, as Gin's debug-mode warning says for production.
ENV GIN_MODE=release
EXPOSE 8080
CMD ["/app/server"]
