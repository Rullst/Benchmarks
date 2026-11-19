import {
  Body,
  Controller,
  Get,
  HttpCode,
  Post,
  Redirect,
  Render,
  Req,
  UnauthorizedException,
  ValidationPipe,
} from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import bcrypt from 'bcrypt';
import type { Session, SessionData } from 'express-session';
import { Repository } from 'typeorm';
import { FormInput, LoginInput } from './dto.js';
import { User } from './user.entity.js';

declare module 'express-session' {
  interface SessionData {
    userId: number;
  }
}

/** The request as express-session leaves it (app.module.ts applies it to these routes only). */
interface SessionRequest {
  session: Session & Partial<SessionData>;
}

/**
 * The browser routes. CSRF: app.enableCsrfProtection() (main.ts) refuses
 * cross-origin POSTs before any handler runs. Sessions: express-session with
 * connect-pg-simple, as middleware of these routes only.
 */
@Controller()
export class BrowserController {
  constructor(
    @InjectRepository(User)
    private readonly users: Repository<User>,
  ) {}

  @Get('form')
  @Render('form')
  form(): Record<string, never> {
    return {};
  }

  @Post('form')
  @HttpCode(200)
  @Render('form-result')
  submitForm(
    @Body(new ValidationPipe({ transform: true, transformOptions: { enableImplicitConversion: true } }))
    input: FormInput,
  ): { name: string; randomNumber: number } {
    return { name: input.name, randomNumber: input.randomNumber };
  }

  @Get('login')
  @Render('login')
  login(): Record<string, never> {
    return {};
  }

  /**
   * bcrypt (the package Nest's hashing chapter names) against
   * users.password_bcrypt, then a new session id (no session fixation) that
   * holds the user's id; express-session stores it when the response ends.
   */
  @Post('login')
  @Redirect('/me', 303)
  async submitLogin(@Req() request: SessionRequest, @Body(new ValidationPipe()) input: LoginInput): Promise<void> {
    const user = await this.users.findOne({
      select: { id: true, passwordBcrypt: true },
      where: { username: input.username },
    });
    if (user === null || !(await bcrypt.compare(input.password, user.passwordBcrypt))) {
      throw new UnauthorizedException();
    }
    await new Promise<void>((resolve, reject) =>
      request.session.regenerate((error: unknown) => (error ? reject(error) : resolve())),
    );
    request.session.userId = user.id;
  }

  /** express-session loads the session from PostgreSQL; the user's row is read on every request. */
  @Get('me')
  async me(@Req() request: SessionRequest): Promise<{ id: number; username: string; displayName: string }> {
    const id = request.session.userId;
    if (id === undefined) {
      throw new UnauthorizedException();
    }
    const user = await this.users.findOne({
      select: { id: true, username: true, displayName: true },
      where: { id },
    });
    if (user === null) {
      throw new UnauthorizedException();
    }
    return { id: user.id, username: user.username, displayName: user.displayName };
  }
}
