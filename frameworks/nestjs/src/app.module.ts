import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { AppController } from './app.controller.js';
import { poolSizePerProcess } from './config.js';
import { World } from './world.entity.js';

@Module({
  imports: [
    TypeOrmModule.forRoot({
      type: 'postgres',
      url: process.env.DATABASE_URL,
      entities: [World],
      poolSize: poolSizePerProcess,
      // The world table already exists: never change the schema.
      synchronize: false,
    }),
    TypeOrmModule.forFeature([World]),
  ],
  controllers: [AppController],
})
export class AppModule {}
