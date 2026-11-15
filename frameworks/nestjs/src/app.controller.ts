import { Controller, Get, Render } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { World } from './world.entity.js';

@Controller()
export class AppController {
  constructor(
    @InjectRepository(World)
    private readonly worlds: Repository<World>,
  ) {}

  @Get('text')
  text(): string {
    return 'Hello World';
  }

  @Get('json')
  json(): { message: string } {
    return { message: 'Hello World' };
  }

  @Get('db-single')
  dbSingle(): Promise<World | null> {
    return this.worlds.findOneBy({ id: 1 });
  }

  @Get('html')
  @Render('hello')
  html(): { name: string } {
    return { name: 'World' };
  }
}
