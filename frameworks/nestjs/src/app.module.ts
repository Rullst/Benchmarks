import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { AuthenticationModule } from '@nestjs/authentication';
import { AppController } from './app.controller.js';
import { AuthSession } from './auth-session.entity.js';
import { BrowserController } from './browser.controller.js';
import { poolSizePerProcess } from './config.js';
import { Fortune } from './fortune.entity.js';
import { SessionAuth } from './session.auth.js';
import { TypeOrmSessionStore } from './session.store.js';
import { User } from './user.entity.js';
import { World } from './world.entity.js';

const entities = [World, Fortune, User, AuthSession];

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
    // No global guard: only GET /me requires a session (@UseGuards).
    AuthenticationModule.forRoot({ globalGuard: false }),
  ],
  controllers: [AppController, BrowserController],
  providers: [TypeOrmSessionStore, SessionAuth],
})
export class AppModule {}
