// The browser routes: /form, /login and /me (docs/v3-spec.md, sections 4-6).
//
// Registered as one encapsulated plugin, so the cookie, session, form body
// and CSRF plugins (and their hooks) apply to these routes only.
// CSRF: @fastify/csrf-protection with @fastify/cookie (its default): the
// secret in the `_csrf` cookie, a token derived from it in the form's `_csrf`
// field. Sessions: @fastify/secure-session, the session encrypted in its
// cookie with SESSION_KEY, which every cluster process shares.
import fastifyCookie from '@fastify/cookie'
import fastifyCsrf from '@fastify/csrf-protection'
import fastifyFormbody from '@fastify/formbody'
import fastifySecureSession from '@fastify/secure-session'
import { compare } from 'bcryptjs'

const USER_ID = 'userId'

const formBody = {
  type: 'object',
  required: ['name', 'randomNumber'],
  properties: {
    _csrf: { type: 'string' },
    name: { type: 'string', minLength: 1, maxLength: 64 },
    randomNumber: { type: 'integer', minimum: 1, maximum: 10000 }
  }
}

const loginBody = {
  type: 'object',
  required: ['username', 'password'],
  properties: {
    _csrf: { type: 'string' },
    username: { type: 'string' },
    password: { type: 'string' }
  }
}

const me = {
  type: 'object',
  properties: { id: { type: 'integer' }, username: { type: 'string' }, displayName: { type: 'string' } }
}

export async function browserRoutes (app, { sessionKey }) {
  await app.register(fastifyCookie)
  await app.register(fastifySecureSession, { key: sessionKey, cookie: { path: '/', httpOnly: true } })
  await app.register(fastifyFormbody)
  await app.register(fastifyCsrf)

  // The token is checked in preValidation: after the body is parsed, before
  // the schema validates the fields (403, then 400).
  const protect = { preValidation: app.csrfProtection }

  app.get('/form', async (request, reply) => {
    return reply.viewAsync('form.ejs', { csrf: reply.generateCsrf() })
  })

  app.post('/form', { ...protect, schema: { body: formBody } }, async (request, reply) => {
    const { name, randomNumber } = request.body
    return reply.viewAsync('form-result.ejs', { name, randomNumber })
  })

  app.get('/login', async (request, reply) => {
    return reply.viewAsync('login.ejs', { csrf: reply.generateCsrf() })
  })

  // bcryptjs (the most-used bcrypt package; Fastify documents none) against
  // users.password_bcrypt, then the user's id in the session.
  app.post('/login', { ...protect, schema: { body: loginBody } }, async (request, reply) => {
    const { username, password } = request.body
    const { rows } = await app.pg.query('SELECT id, password_bcrypt FROM users WHERE username = $1', [username])
    if (rows.length === 0 || !(await compare(password, rows[0].password_bcrypt))) {
      return reply.code(401).send({ message: 'Invalid credentials' })
    }
    request.session.set(USER_ID, rows[0].id)
    return reply.redirect('/me', 303)
  })

  // The session cookie is decrypted by the plugin; the user's row is read on every request.
  app.get('/me', { schema: { response: { 200: me } } }, async (request, reply) => {
    const id = request.session.get(USER_ID)
    if (id === undefined) return reply.code(401).send({ message: 'Unauthorized' })
    const { rows } = await app.pg.query('SELECT id, username, display_name FROM users WHERE id = $1', [id])
    if (rows.length === 0) return reply.code(401).send({ message: 'Unauthorized' })
    return { id: rows[0].id, username: rows[0].username, displayName: rows[0].display_name }
  })
}
