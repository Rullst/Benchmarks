# Spring Boot

| | |
| --- | --- |
| Version | Spring Boot 4.1.2, which pins Spring Framework 7.0, Spring Data JPA, Hibernate 7.4, Tomcat 11.0, Thymeleaf 3.1, HikariCP 7.0 and the PostgreSQL JDBC driver 42.7 (the resolved jars are listed in `/bench/versions.txt` in the image) |
| Build | `mvn package` with Maven 3.10.0 on Eclipse Temurin 25; the executable jar is extracted into layers with `java -Djarmode=tools -jar application.jar extract --layers` and started with `java -jar application.jar` |
| Server | Spring MVC on embedded Tomcat, the default of `spring-boot-starter-webmvc`, with Tomcat's default request thread pool (up to 200 threads) |
| JVM | Eclipse Temurin 25.0.5 JRE (Java 25 LTS) with no JVM flags: the JVM sizes itself from the container (2 vCPUs, 2 GiB), so it uses G1 and a maximum heap of 25% of the memory limit (512 MiB) |
| Database | Spring Data JPA, `JpaRepository.findById(1)` (Hibernate); HikariCP `maximum-pool-size` = `DB_POOL_SIZE` (16); `ddl-auto=none`; `Application.main` translates `DATABASE_URL` into the JDBC URL and credentials |
| Templates | Thymeleaf (`src/main/resources/templates/hello.html`) with Spring Boot's defaults (template cache on) |
| Logging | Spring Boot's default: start-up messages at INFO, nothing per request (Tomcat's access log is off by default) |
| Image | `eclipse-temurin:25.0.5_8-jre-noble` |

Lockfile: Maven has no lockfile. The `spring-boot-starter-parent` 4.1.2
parent fixes the version of every dependency (its `spring-boot-dependencies`
BOM) and of every plugin the build runs (compiler, resources, jar, surefire,
`spring-boot-maven-plugin`), and the Maven version is fixed by the build
image tag, so the build resolves the same artifacts every time.

Why:

- The image is the multi-stage Dockerfile of the Spring Boot reference
  documentation ([Dockerfiles](https://docs.spring.io/spring-boot/reference/packaging/container-images/dockerfiles.html)):
  extract the layered jar in a builder stage, copy the four layers, start
  `application.jar`. The documentation's example uses a Liberica image; this
  one uses Eclipse Temurin. The same page offers an AOT cache for Java 25 as
  an optional addition; it is not used, because its training run starts the
  application context (and so connects to the database) during the image
  build, and it speeds up start-up and warm-up rather than serving.
- That Dockerfile passes no JVM options, so the JVM's container ergonomics
  apply. `spring-boot:build-image` would instead set `-Xmx` with the Paketo
  memory calculator; the Dockerfile route the documentation describes does
  not, and the Spring documentation does not recommend heap flags for it.
- [SQL databases](https://docs.spring.io/spring-boot/reference/data/sql.html):
  Spring Boot prefers HikariCP and configures it through
  `spring.datasource.hikari.*`; `ddl-auto` is `none` for a non-embedded
  database, set here explicitly because the table already exists.
- Open EntityManager in View stays on (Spring Boot's default). The
  documentation only says to set `spring.jpa.open-in-view=false` "if you do not
  want this behavior" and does not recommend it for production; the property
  is set to `true` explicitly to document the choice and silence the start-up
  warning.
- Everything else is Spring Boot's default: no virtual threads
  (`spring.threads.virtual.enabled` is off by default), no Hibernate
  second-level or query cache, no extra filters.
