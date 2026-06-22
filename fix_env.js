const fs = require('fs');
let content = fs.readFileSync('docker-compose.yml', 'utf8');

content = content.replace(
  /  quarkus:[\s\S]*?environment:[\s\S]*?- PORT=3000/,
  `  quarkus:
    build:
      context: ./quarkus
      dockerfile: Dockerfile
    environment:
      - QUARKUS_DATASOURCE_JDBC_URL=jdbc:postgresql://db:5432/bench
      - QUARKUS_DATASOURCE_USERNAME=postgres
      - QUARKUS_DATASOURCE_PASSWORD=postgres
      - PORT=3000`
);

content = content.replace(
  /  springboot:[\s\S]*?environment:[\s\S]*?- PORT=3000/,
  `  springboot:
    build:
      context: ./springboot
      dockerfile: Dockerfile
    environment:
      - SPRING_DATASOURCE_URL=jdbc:postgresql://db:5432/bench
      - SPRING_DATASOURCE_USERNAME=postgres
      - SPRING_DATASOURCE_PASSWORD=postgres
      - PORT=3000`
);

fs.writeFileSync('docker-compose.yml', content);
