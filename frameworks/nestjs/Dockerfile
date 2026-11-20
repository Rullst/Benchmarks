# `docker build --target lockfile --output <dir>` updates package-lock.json
# from package.json (npm is not needed locally); the image itself installs
# from the committed lockfile.
FROM node:26.13.1-trixie-slim AS resolve
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm install --package-lock-only --no-audit --no-fund

FROM scratch AS lockfile
COPY --from=resolve /app/package-lock.json /

# Compile with the Nest CLI (`nest build`, tsc), then keep only the
# production dependencies, as the Nest deployment guide suggests.
FROM node:26.13.1-trixie-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY nest-cli.json tsconfig.json tsconfig.build.json ./
COPY src ./src
RUN npm run build && npm prune --omit=dev --no-audit --no-fund
# Record the resolved versions of the main packages for the results.
RUN node -e 'const fs = require("node:fs"); \
      for (const name of ["@nestjs/core", "@nestjs/platform-node", "@nestjs/typeorm", "typeorm", "pg", "hbs", "handlebars", "class-validator", "bcrypt", "express-session", "connect-pg-simple"]) \
        console.log(name, JSON.parse(fs.readFileSync(`node_modules/${name}/package.json`, "utf8")).version); \
      console.log("node", process.versions.node);' > versions.txt \
    && cat versions.txt

FROM node:26.13.1-trixie-slim
ENV NODE_ENV=production
WORKDIR /app
COPY --from=build /app/package.json ./
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/dist ./dist
COPY views ./views
COPY --from=build /app/versions.txt /bench/versions.txt
EXPOSE 8080
USER node
CMD ["node", "dist/main.js"]
