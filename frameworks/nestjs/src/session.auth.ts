import { Injectable } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import {
  AuthenticationRegistry,
  SessionCookieProvider,
  type SessionRecord,
} from '@nestjs/authentication';
import { Repository } from 'typeorm';
import { User } from './user.entity.js';

/**
 * Cookie sessions of @nestjs/authentication: the session is read from the
 * store, then its user from `users`, on every request.
 */
@Injectable()
export class SessionAuth extends SessionCookieProvider<User> {
  constructor(
    @InjectRepository(User)
    private readonly users: Repository<User>,
    registry: AuthenticationRegistry,
  ) {
    super();
    registry.registerProvider(this);
  }

  protected validate(session: SessionRecord): Promise<User | null> {
    return this.users.findOne({
      select: { id: true, username: true, displayName: true },
      where: { id: Number(session.userId) },
    });
  }
}
