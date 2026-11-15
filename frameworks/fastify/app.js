// Fastify: the suite's four endpoints with @fastify/postgres and @fastify/view (EJS).
import path from 'node:path'
import Fastify from 'fastify'
import fastifyPostgres from '@fastify/postgres'
import fastifyView from '@fastify/view'
import ejs from 'ejs'

// Response schemas, as the Fastify recommendations advise for JSON routes.
const message = {
  type: 'object',
  properties: { message: { type: 'string' } }
}
const world = {
  type: 'object',
  properties: { id: { type: 'integer' }, randomNumber: { type: 'integer' } }
}

export function build ({ connectionString, poolSize }) {
  // The logger is off by default.
  const app = Fastify()
  // Options are passed to the node-postgres Pool.
  app.register(fastifyPostgres, { connectionString, max: poolSize })
  // With NODE_ENV=production, @fastify/view caches the compiled template.
  app.register(fastifyView, { engine: { ejs }, root: path.join(import.meta.dirname, 'views') })

  app.get('/text', async () => 'Hello World')

  app.get('/json', { schema: { response: { 200: message } } }, async () => {
    return { message: 'Hello World' }
  })

  app.get('/db-single', { schema: { response: { 200: world } } }, async () => {
    const { rows } = await app.pg.query('SELECT id, randomnumber FROM world WHERE id = $1', [1])
    return { id: rows[0].id, randomNumber: rows[0].randomnumber }
  })

  app.get('/html', async (request, reply) => {
    return reply.viewAsync('hello.ejs', { name: 'World' })
  })

  return app
}
