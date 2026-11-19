import { Column, Entity, PrimaryColumn } from 'typeorm';

/**
 * A row of `auth_session` (db.sql): what @nestjs/authentication's
 * `SessionStore` keeps for a session. `id` is the SHA-256 of the cookie token.
 */
@Entity('auth_session')
export class AuthSession {
  @PrimaryColumn({ type: 'text' })
  id: string;

  @Column({ name: 'user_id', type: 'text' })
  userId: string;

  @Column({ name: 'created_at', type: 'timestamptz' })
  createdAt: Date;

  @Column({ name: 'expires_at', type: 'timestamptz' })
  expiresAt: Date;

  @Column({ name: 'last_active_at', type: 'timestamptz' })
  lastActiveAt: Date;

  @Column({ type: 'text', nullable: true })
  mfa: string | null;

  @Column({ type: 'jsonb', nullable: true })
  metadata: object | null;
}
