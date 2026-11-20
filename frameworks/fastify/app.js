// Fastify: the suite's endpoints with @fastify/postgres and @fastify/view (EJS).
import path from 'node:path'
import Fastify from 'fastify'
import fastifyPostgres from '@fastify/postgres'
import fastifyView from '@fastify/view'
import Ajv from 'ajv'
import ejs from 'ejs'
import { browserRoutes } from './browser.js'

// Response schemas, as the Fastify recommendations advise for JSON routes.
const message = {
  type: 'object',
  properties: { message: { type: 'string' } }
}
const world = {
  type: 'object',
  properties: { id: { type: 'integer' }, randomNumber: { type: 'integer' } }
}
const worldList = { type: 'array', items: world }

const SELECT_WORLD = 'SELECT id, randomnumber FROM world WHERE id = $1'
const idParams = {
  type: 'object',
  required: ['id'],
  properties: { id: { type: 'integer' } }
}

// Fastify's validator coerces types in every part of the request (its Ajv
// option coerceTypes: 'array'), so {"randomNumber": "5"} would pass as 5. The
// Validation and Serialization reference shows a validator compiler per
// httpPart for this; PUT /world/:id uses one that does not coerce the JSON body.
const ajvOptions = { useDefaults: true, removeAdditional: true, allErrors: false }
const coercing = new Ajv({ ...ajvOptions, coerceTypes: 'array' })
const strict = new Ajv({ ...ajvOptions, coerceTypes: false })
const strictBody = ({ schema, httpPart }) => (httpPart === 'body' ? strict : coercing).compile(schema)

// The queries parameter: an integer clamped to 1..500, otherwise 1.
function queryCount (value) {
  const count = /^\s*[-+]?\d+\s*$/.test(value ?? '') ? Number.parseInt(value, 10) : 1
  return Math.min(500, Math.max(1, count))
}

function randomId () {
  return 1 + Math.floor(Math.random() * 10000)
}

// A new random number, different from the current one so that every row is written.
function newRandomNumber (current) {
  let value = randomId()
  while (value === current) value = randomId()
  return value
}

export function build ({ connectionString, poolSize, sessionKey }) {
  // The logger is off by default.
  const app = Fastify()
  // Options are passed to the node-postgres Pool.
  app.register(fastifyPostgres, { connectionString, max: poolSize })
  // With NODE_ENV=production, @fastify/view caches the compiled template.
  app.register(fastifyView, { engine: { ejs }, root: path.join(import.meta.dirname, 'views') })
  // /form, /login and /me with their plugins, encapsulated: the other
  // routes do not run their hooks.
  app.register(browserRoutes, { sessionKey })

  const readWorld = async (id) => {
    const { rows } = await app.pg.query(SELECT_WORLD, [id])
    return { id: rows[0].id, randomNumber: rows[0].randomnumber }
  }

  app.get('/text', async () => 'Hello World')

  app.get('/json', { schema: { response: { 200: message } } }, async () => {
    return { message: 'Hello World' }
  })

  app.get('/db-single', { schema: { response: { 200: world } } }, async () => readWorld(1))

  app.get('/html', async (request, reply) => {
    return reply.viewAsync('hello.ejs', { name: 'World' })
  })

  // One query per random id, run concurrently on the process's pool.
  app.get('/queries', { schema: { response: { 200: worldList } } }, async (request) => {
    const ids = Array.from({ length: queryCount(request.query.queries) }, randomId)
    return Promise.all(ids.map(readWorld))
  })

  // Each row is read with its own query, given a new value and written with
  // its own UPDATE (no transaction).
  app.get('/updates', { schema: { response: { 200: worldList } } }, async (request) => {
    const ids = Array.from({ length: queryCount(request.query.queries) }, randomId)
    const worlds = await Promise.all(ids.map(readWorld))
    for (const row of worlds) row.randomNumber = newRandomNumber(row.randomNumber)
    await Promise.all(worlds.map((row) =>
      app.pg.query('UPDATE world SET randomnumber = $1 WHERE id = $2', [row.randomNumber, row.id])))
    return worlds
  })

  // Every fortune (no ORDER BY), plus one added here, sorted by message (UTF-16 code units).
  app.get('/fortunes', async (request, reply) => {
    const { rows } = await app.pg.query('SELECT id, message FROM fortune')
    rows.push({ id: 0, message: 'Additional fortune added at request time.' })
    rows.sort((a, b) => (a.message < b.message ? -1 : a.message > b.message ? 1 : 0))
    return reply.viewAsync('fortunes.ejs', { fortunes: rows })
  })

  // The params schema rejects a non-integer id (400); no row is a 404.
  app.get('/world/:id', { schema: { params: idParams, response: { 200: world } } }, async (request, reply) => {
    const { rows } = await app.pg.query(SELECT_WORLD, [request.params.id])
    if (rows.length === 0) return reply.code(404).send({ message: 'Not Found' })
    return { id: rows[0].id, randomNumber: rows[0].randomnumber }
  })

  // One query: filter, order and paginate in PostgreSQL.
  const worldsQuery = {
    type: 'object',
    properties: {
      min: { type: 'integer', minimum: 1, maximum: 10000, default: 1 },
      max: { type: 'integer', minimum: 1, maximum: 10000, default: 10000 },
      limit: { type: 'integer', minimum: 1, maximum: 100, default: 20 },
      page: { type: 'integer', minimum: 1, maximum: 1000, default: 1 }
    }
  }
  app.get('/worlds', { schema: { querystring: worldsQuery, response: { 200: worldList } } }, async (request, reply) => {
    const { min, max, limit, page } = request.query
    if (min > max) return reply.code(400).send({ message: 'min must not exceed max' })
    const { rows } = await app.pg.query(
      'SELECT id, randomnumber FROM world WHERE id BETWEEN $1 AND $2 ORDER BY id LIMIT $3 OFFSET $4',
      [min, max, limit, (page - 1) * limit])
    return rows.map((row) => ({ id: row.id, randomNumber: row.randomnumber }))
  })

  // No ORM: one UPDATE ... RETURNING, after the body schema has accepted the body.
  const worldUpdate = {
    type: 'object',
    required: ['randomNumber'],
    properties: { randomNumber: { type: 'integer', minimum: 1, maximum: 10000 } }
  }
  app.put('/world/:id', {
    schema: { params: idParams, body: worldUpdate, response: { 200: world } },
    validatorCompiler: strictBody
  }, async (request, reply) => {
    const { rows } = await app.pg.query(
      'UPDATE world SET randomnumber = $1 WHERE id = $2 RETURNING id, randomnumber',
      [request.body.randomNumber, request.params.id])
    if (rows.length === 0) return reply.code(404).send({ message: 'Not Found' })
    return { id: rows[0].id, randomNumber: rows[0].randomnumber }
  })

  return app
}
