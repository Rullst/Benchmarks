# Resolve the NuGet packages and export packages.lock.json (CI uploads the
# `lockfile` stage's output; the image below builds from the committed file).
FROM mcr.microsoft.com/dotnet/sdk:10.0.404-noble@sha256:bef136a371963aaa46ec97882845ef6f54dec15728bb4b128b1c2a400ffbc9b4 AS resolve
WORKDIR /src
COPY AspNetCoreBench.csproj ./
RUN dotnet restore

FROM scratch AS lockfile
COPY --from=resolve /src/packages.lock.json /

# Release build, as in Microsoft's "Containerize a .NET app" Dockerfile:
# restore with the committed lockfile, then a framework-dependent publish.
FROM mcr.microsoft.com/dotnet/sdk:10.0.404-noble@sha256:bef136a371963aaa46ec97882845ef6f54dec15728bb4b128b1c2a400ffbc9b4 AS build
WORKDIR /src
COPY AspNetCoreBench.csproj packages.lock.json ./
RUN dotnet restore --locked-mode
COPY Program.cs appsettings.json ./
COPY Pages ./Pages
RUN dotnet publish --no-restore --configuration Release --output /app
# Record the resolved versions of the main packages for the results.
RUN awk '/^      "[^"]+": \{$/ { name = $1; gsub(/[":]/, "", name) } \
         /^        "resolved": / { version = $2; gsub(/[",]/, "", version); print name, version }' \
        packages.lock.json \
    | grep -E '^(Microsoft\.EntityFrameworkCore|Microsoft\.EntityFrameworkCore\.Relational|Npgsql|Npgsql\.EntityFrameworkCore\.PostgreSQL|BCrypt\.Net-Next) ' \
    | sort > /versions.txt \
    && cat /versions.txt

FROM mcr.microsoft.com/dotnet/aspnet:10.0.15-noble@sha256:12b1135f5f8b3c0a214f2a680ff2033dff4f684f445d6c697d9524ceeb303586
WORKDIR /app
COPY --from=build /app ./
COPY --from=build /versions.txt /bench/versions.txt
RUN printf 'Microsoft.AspNetCore.App %s\n' "$(ls /usr/share/dotnet/shared/Microsoft.AspNetCore.App)" >> /bench/versions.txt \
    && cat /bench/versions.txt
EXPOSE 8080
USER $APP_UID
ENTRYPOINT ["dotnet", "AspNetCoreBench.dll"]
