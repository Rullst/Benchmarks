import {
  BadRequestException,
  Body,
  Controller,
  Get,
  NotFoundException,
  Param,
  ParseIntPipe,
  Put,
  Query,
  Render,
  ValidationPipe,
} from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Between, Repository } from 'typeorm';
import { WorldsQuery, WorldUpdate } from './dto.js';
import { Fortune } from './fortune.entity.js';
import { World } from './world.entity.js';

/** The queries parameter: an integer clamped to 1..500, otherwise 1. */
function queryCount(value: string | undefined): number {
  const count = /^\s*[-+]?\d+\s*$/.test(value ?? '') ? Number.parseInt(value ?? '', 10) : 1;
  return Math.min(500, Math.max(1, count));
}

function randomId(): number {
  return 1 + Math.floor(Math.random() * 10000);
}

/** A new random number, different from the current one so that every row is written. */
function newRandomNumber(current: number): number {
  let value = randomId();
  while (value === current) {
    value = randomId();
  }
  return value;
}

function found<T>(row: T | null): T {
  if (row === null) {
    throw new NotFoundException();
  }
  return row;
}

@Controller()
export class AppController {
  constructor(
    @InjectRepository(World)
    private readonly worlds: Repository<World>,
    @InjectRepository(Fortune)
    private readonly fortunes: Repository<Fortune>,
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

  /** One findOneBy per random id, run concurrently on the process's pool. */
  @Get('queries')
  queries(@Query('queries') queries?: string): Promise<World[]> {
    const ids = Array.from({ length: queryCount(queries) }, randomId);
    return Promise.all(ids.map(async (id) => found(await this.worlds.findOneBy({ id }))));
  }

  /**
   * Each row is read with its own findOneBy, given a new value, and written
   * with its own Repository.update() (one UPDATE per row, no transaction).
   */
  @Get('updates')
  async updates(@Query('queries') queries?: string): Promise<World[]> {
    const ids = Array.from({ length: queryCount(queries) }, randomId);
    const worlds = await Promise.all(ids.map(async (id) => found(await this.worlds.findOneBy({ id }))));
    for (const world of worlds) {
      world.randomNumber = newRandomNumber(world.randomNumber);
    }
    await Promise.all(
      worlds.map((world) => this.worlds.update({ id: world.id }, { randomNumber: world.randomNumber })),
    );
    return worlds;
  }

  /** Every fortune (no ORDER BY), plus one added here, sorted by message (UTF-16 code units). */
  @Get('fortunes')
  @Render('fortunes')
  async fortuneList(): Promise<{ fortunes: { id: number; message: string }[] }> {
    const rows = await this.fortunes.find();
    const fortunes = rows.map(({ id, message }) => ({ id, message }));
    fortunes.push({ id: 0, message: 'Additional fortune added at request time.' });
    fortunes.sort((a, b) => (a.message < b.message ? -1 : a.message > b.message ? 1 : 0));
    return { fortunes };
  }

  /** ParseIntPipe: a non-integer id is a 400; no row is a 404. */
  @Get('world/:id')
  async world(@Param('id', ParseIntPipe) id: number): Promise<World> {
    return found(await this.worlds.findOneBy({ id }));
  }

  /** One query: filter, order and paginate in PostgreSQL. */
  @Get('worlds')
  async worldList(
    @Query(new ValidationPipe({ transform: true, transformOptions: { enableImplicitConversion: true } }))
    query: WorldsQuery,
  ): Promise<World[]> {
    if (query.min > query.max) {
      throw new BadRequestException('min must not exceed max');
    }
    return this.worlds.find({
      where: { id: Between(query.min, query.max) },
      order: { id: 'ASC' },
      skip: (query.page - 1) * query.limit,
      take: query.limit,
    });
  }

  /** The body is validated (400) before the row is loaded, changed and saved. */
  @Put('world/:id')
  async updateWorld(
    @Param('id', ParseIntPipe) id: number,
    @Body(new ValidationPipe()) body: WorldUpdate,
  ): Promise<World> {
    const world = found(await this.worlds.findOneBy({ id }));
    world.randomNumber = body.randomNumber;
    return this.worlds.save(world);
  }
}
