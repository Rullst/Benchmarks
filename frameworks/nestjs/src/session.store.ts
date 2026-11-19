import { Injectable } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import {
  AuthenticationStorage,
  type MfaState,
  type SessionRecord,
  type SessionStore,
} from '@nestjs/authentication';
import { LessThan, Repository } from 'typeorm';
import { AuthSession } from './auth-session.entity.js';

function toRecord(row: AuthSession): SessionRecord {
  return {
    id: row.id,
    userId: row.userId,
    createdAt: row.createdAt,
    expiresAt: row.expiresAt,
    lastActiveAt: row.lastActiveAt,
    ...(row.mfa !== null && { mfa: row.mfa as MfaState }),
    ...(row.metadata !== null && { metadata: row.metadata as Record<string, unknown> }),
  };
}

/**
 * The PostgreSQL session store of @nestjs/authentication, through TypeORM.
 * The package ships in-memory stores only and asks for a real one in
 * production (`AuthenticationStorage.registerSource()`); each method follows
 * the rule its `SessionStore` documentation gives.
 */
@Injectable()
export class TypeOrmSessionStore implements SessionStore {
  constructor(
    @InjectRepository(AuthSession)
    private readonly sessions: Repository<AuthSession>,
    storage: AuthenticationStorage,
  ) {
    storage.registerSource({ sessions: this });
  }

  async getSession(id: string): Promise<SessionRecord | undefined> {
    const row = await this.sessions.findOneBy({ id });
    return row ? toRecord(row) : undefined;
  }

  async createSession(record: SessionRecord): Promise<void> {
    await this.sessions.insert({
      id: record.id,
      userId: record.userId,
      createdAt: record.createdAt,
      expiresAt: record.expiresAt,
      lastActiveAt: record.lastActiveAt,
      mfa: record.mfa ?? null,
      metadata: record.metadata ?? null,
    });
  }

  /** One conditional write: only an existing session, and only forward. */
  async touchSession(id: string, lastActiveAt: Date): Promise<void> {
    await this.sessions.update({ id, lastActiveAt: LessThan(lastActiveAt) }, { lastActiveAt });
  }

  async deleteSession(id: string): Promise<boolean> {
    const result = await this.sessions.delete({ id });
    return (result.affected ?? 0) > 0;
  }

  async listUserSessions(userId: string): Promise<SessionRecord[]> {
    const rows = await this.sessions.findBy({ userId });
    return rows.map(toRecord);
  }

  async deleteUserSessions(userId: string): Promise<void> {
    await this.sessions.delete({ userId });
  }
}
