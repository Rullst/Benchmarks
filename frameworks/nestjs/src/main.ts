import cluster from 'node:cluster';
import { join } from 'node:path';
import { NestFactory } from '@nestjs/core';
import { NestNodeApplication, NodeAdapter } from '@nestjs/platform-node';
import { AppModule } from './app.module.js';
import { port, workers } from './config.js';

async function bootstrap(): Promise<void> {
  const app = await NestFactory.create<NestNodeApplication>(AppModule, new NodeAdapter());
  app.setBaseViewsDir(join(import.meta.dirname, '..', 'views'));
  app.setViewEngine('hbs');
  // There is no layout file: hbs's `layout: false`, set for every view
  // through the `layout` local (as Nest's MVC chapter sets an hbs layout),
  // renders each view on its own instead of trying views/layout.hbs first.
  app.setLocal('layout', false);
  // Built-in CSRF protection (Nest 12.1+): unsafe requests whose
  // Sec-Fetch-Site or Origin shows another origin are refused (403).
  app.enableCsrfProtection();
  await app.listen(port, '0.0.0.0');
}

if (cluster.isPrimary) {
  // One Nest process per vCPU; the primary only distributes connections.
  for (let i = 0; i < workers; i++) {
    cluster.fork();
  }
  // A worker that dies stops the server, so a crash is visible instead of
  // leaving fewer processes running.
  cluster.on('exit', (worker, code, signal) => {
    console.error(`worker ${worker.process.pid} exited (${signal ?? code})`);
    process.exit(1);
  });
  // As PID 1 in the container, Node has no default SIGTERM handler.
  process.on('SIGTERM', () => process.exit(0));
} else {
  await bootstrap();
}
