# Node.js 26 (the active LTS release), production dependencies from the lockfile.
FROM node:26.13.1-trixie-slim@sha256:e6bedef217677b276c591795e169840edd9096dbf13f29df8ef8d1856b8820bc
ENV NODE_ENV=production
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --no-audit --no-fund && npm cache clean --force
COPY app.js server.js ./
COPY views ./views
# Record the resolved versions of the main packages for the results.
RUN mkdir /bench && node -e "const fs = require('node:fs'); \
console.log('node', process.versions.node); \
for (const n of ['fastify', '@fastify/postgres', 'pg', '@fastify/view', 'ejs']) \
  console.log(n, JSON.parse(fs.readFileSync('node_modules/' + n + '/package.json', 'utf8')).version)" \
    > /bench/versions.txt && cat /bench/versions.txt
USER node
EXPOSE 8080
# node directly (not npm start), so the server process receives the signals.
CMD ["node", "server.js"]
