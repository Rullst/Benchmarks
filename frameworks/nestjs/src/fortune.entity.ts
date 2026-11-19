import { Column, Entity, PrimaryColumn } from 'typeorm';

@Entity('fortune')
export class Fortune {
  @PrimaryColumn()
  id: number;

  @Column()
  message: string;
}
