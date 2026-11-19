import { Column, Entity, PrimaryColumn } from 'typeorm';

/** A row of the phase-2 `users` table. */
@Entity('users')
export class User {
  @PrimaryColumn()
  id: number;

  @Column()
  username: string;

  @Column({ name: 'display_name' })
  displayName: string;

  @Column({ name: 'password_bcrypt' })
  passwordBcrypt: string;
}
