import {
  Body,
  Controller,
  Get,
  HttpCode,
  Post,
  Redirect,
  Render,
  UnauthorizedException,
  UseGuards,
  ValidationPipe,
} from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { AuthenticationGuard, CurrentUser, SignInService } from '@nestjs/authentication';
import bcrypt from 'bcrypt';
import { Repository } from 'typeorm';
import { FormInput, LoginInput } from './dto.js';
import { User } from './user.entity.js';

/**
 * The browser routes. CSRF: app.enableCsrfProtection() (main.ts) refuses
 * cross-origin POSTs before any handler runs. Sessions: @nestjs/authentication.
 */
@Controller()
export class BrowserController {
  constructor(
    @InjectRepository(User)
    private readonly users: Repository<User>,
    private readonly signIn: SignInService,
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

  /** bcrypt (the package Nest's hashing chapter names) against users.password_bcrypt, then a server-side session. */
  @Post('login')
  @Redirect('/me', 303)
  async submitLogin(@Body(new ValidationPipe()) input: LoginInput): Promise<void> {
    const user = await this.users.findOne({
      select: { id: true, passwordBcrypt: true },
      where: { username: input.username },
    });
    if (user === null || !(await bcrypt.compare(input.password, user.passwordBcrypt))) {
      throw new UnauthorizedException();
    }
    await this.signIn.signIn(String(user.id), { method: 'password' });
  }

  /** The guard resolves the session and loads the user's row (SessionAuth) on every request. */
  @Get('me')
  @UseGuards(AuthenticationGuard)
  me(@CurrentUser() user: User): { id: number; username: string; displayName: string } {
    return { id: user.id, username: user.username, displayName: user.displayName };
  }
}
