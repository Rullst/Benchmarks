import { type MiddlewareConsumer, Module, type NestModule } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import connectPgSimple from 'connect-pg-simple';
import session from 'express-session';
import type { Pool } from 'pg';
import { DataSource } from 'typeorm';
import { AppController } from './app.controller.js';
import { BrowserController } from './browser.controller.js';
import { poolSizePerProcess, sessionSecret } from './config.js';
import { Fortune } from './fortune.entity.js';
import { User } from './user.entity.js';
import { World } from './world.entity.js';

const entities = [World, Fortune, User];

@Module({
  imports: [
    TypeOrmModule.forRoot({
      type: 'postgres',
      url: process.env.DATABASE_URL,
      entities,
      poolSize: poolSizePerProcess,
      // The tables already exist: never change the schema.
      synchronize: false,
    }),
    TypeOrmModule.forFeature(entities),
  ],
  controllers: [AppController, BrowserController],
})
export class AppModule implements NestModule {
  constructor(private readonly dataSource: DataSource) {}

  /**
   * express-session with its PostgreSQL store, connect-pg-simple (table in
   * db.sql), on the browser routes only. The store queries through TypeORM's
   * pg pool (PostgresDriver.master), so the process keeps one pool of
   * DB_POOL_SIZE / BENCH_WORKERS connections.
   */
  configure(consumer: MiddlewareConsumer): void {
    const PgStore = connectPgSimple(session);
    const pool = (this.dataSource.driver as unknown as { master: Pool }).master;
    consumer
      .apply(
        session({
          store: new PgStore({ pool }),
          secret: sessionSecret,
          resave: false,
          saveUninitialized: false,
        }),
      )
      .forRoutes('form', 'login', 'me');
  }
}
