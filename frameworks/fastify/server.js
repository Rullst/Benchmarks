// One Fastify process per vCPU with node:cluster (BENCH_WORKERS), each with
// DB_POOL_SIZE / BENCH_WORKERS database connections.
import cluster from 'node:cluster'
import process from 'node:process'
import { build } from './app.js'

const workers = Number(process.env.BENCH_WORKERS ?? 2)

if (cluster.isPrimary) {
  for (let i = 0; i < workers; i++) cluster.fork()
  // A worker that exits stops the server, so a crash is reported, not hidden
  // by a restart.
  cluster.on('exit', (worker, code, signal) => {
    console.error(`worker ${worker.process.pid} exited (${signal ?? code})`)
    process.exit(1)
  })
  // The primary is PID 1 in the container: exit on `docker stop`; the
  // workers end with it.
  for (const signal of ['SIGTERM', 'SIGINT']) process.on(signal, () => process.exit(0))
} else {
  // The session encryption key (32 bytes, hex): the same in every worker, so
  // a session cookie set by one process opens in the other (bench.json `env`).
  const sessionKey = Buffer.from(process.env.SESSION_KEY ?? '', 'hex')
  if (sessionKey.length !== 32) throw new Error('SESSION_KEY must be 64 hexadecimal characters')
  const app = build({
    connectionString: process.env.DATABASE_URL,
    poolSize: Math.max(1, Math.floor(Number(process.env.DB_POOL_SIZE ?? 16) / workers)),
    sessionKey
  })
  // 0.0.0.0, as the Fastify recommendations say for containers.
  await app.listen({ host: '0.0.0.0', port: Number(process.env.PORT ?? 8080) })
}
