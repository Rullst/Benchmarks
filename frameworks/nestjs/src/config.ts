import { availableParallelism } from 'node:os';

function positiveInteger(value: string | undefined, fallback: number): number {
  const parsed = Number.parseInt(value ?? '', 10);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback;
}

/** Server processes: one per vCPU (BENCH_WORKERS), the suite's Node.js convention. */
export const workers = positiveInteger(process.env.BENCH_WORKERS, availableParallelism());

/** DB_POOL_SIZE is the total for the server, so each process gets its share. */
export const poolSizePerProcess = Math.max(
  1,
  Math.floor(positiveInteger(process.env.DB_POOL_SIZE, 16) / workers),
);

export const port = positiveInteger(process.env.PORT, 8080);

/**
 * The secret express-session signs its cookie with: the same in every
 * cluster process (bench.json `env`), so each one accepts the others' cookies.
 */
export const sessionSecret = process.env.SESSION_SECRET ?? '';
if (sessionSecret === '') {
  throw new Error('SESSION_SECRET must be set');
}
