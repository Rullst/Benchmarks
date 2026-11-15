import { Column, Entity, PrimaryColumn } from 'typeorm';

@Entity('world')
export class World {
  @PrimaryColumn()
  id: number;

  @Column({ name: 'randomnumber' })
  randomNumber: number;
}
