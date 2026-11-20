# Spring Boot

| | |
| --- | --- |
| Version | Spring Boot 4.1.2, which pins Spring Framework 7.0, Spring Data JPA, Hibernate 7.4, Tomcat 11.0, Thymeleaf 3.1, HikariCP 7.0 and the PostgreSQL JDBC driver 42.7 (the resolved jars are listed in `/bench/versions.txt` in the image) |
| Build | `mvn package` with Maven 3.10.0 on Eclipse Temurin 25; the executable jar is extracted into layers with `java -Djarmode=tools -jar application.jar extract --layers` and started with `java -jar application.jar` |
| Server | Spring MVC on embedded Tomcat, the default of `spring-boot-starter-webmvc`, with Tomcat's default request thread pool (up to 200 threads) |
| JVM | Eclipse Temurin 25.0.5 JRE (Java 25 LTS) with no JVM flags: the JVM sizes itself from the container (2 vCPUs, 2 GiB), so it uses G1 and a maximum heap of 25% of the memory limit (512 MiB) |
| Database | Spring Data JPA (Hibernate) entities `World`, `Fortune` and `Account` (`users`); HikariCP `maximum-pool-size` = `DB_POOL_SIZE` (16); `ddl-auto=none`; `open-in-view=false`; `Application.main` translates `DATABASE_URL` into the JDBC URL and credentials |
| Templates | Thymeleaf (`src/main/resources/templates/`) with Spring Boot's defaults (template cache on) |
| Validation | `spring-boot-starter-validation` (Hibernate Validator): constraints on `@RequestParam`s (Spring MVC's built-in method validation), `@Valid @RequestBody` and `@Valid @ModelAttribute` records; failures answer 400 |
| CSRF, sessions | `spring-boot-starter-security`, one `SecurityFilterChain` with `securityMatcher("/form", "/login", "/me")`: Spring Security's default CSRF protection, form login (`loginPage("/login")`) and the `SecurityContext` in Tomcat's in-memory `HttpSession` |
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
- Open EntityManager in View is off (`spring.jpa.open-in-view=false`), as
  the documentation says to do when the application does not need lazy
  loading in its views (see Production settings).
- Everything else is Spring Boot's default: no virtual threads
  (`spring.threads.virtual.enabled` is off by default), no Hibernate
  second-level or query cache, no extra filters.

## Production settings

| Setting | Value | Source |
| --- | --- | --- |
| Logging | Spring Boot's default: `INFO` to the console, so start-up lines only; nothing per request (Tomcat's access log is off by default, `spring.jpa.show-sql` is `false`) | [Logging](https://docs.spring.io/spring-boot/reference/features/logging.html): "By default, `ERROR`-level, `WARN`-level, and `INFO`-level messages are logged"; [`server.tomcat.accesslog.enabled`](https://docs.spring.io/spring-boot/appendix/application-properties/index.html#application-properties.server.server.tomcat.accesslog.enabled), [`spring.jpa.show-sql`](https://docs.spring.io/spring-boot/appendix/application-properties/index.html#application-properties.data.spring.jpa.show-sql) |
| Open EntityManager in View | `spring.jpa.open-in-view=false`. When on, its interceptor opens a JPA `EntityManager` for every Spring MVC request (`/text` and `/json` included), and the connection a request has used stays checked out of the pool until the view is rendered. No entity here has a lazy association, so nothing needs it | [Open EntityManager in View](https://docs.spring.io/spring-boot/reference/data/sql.html#data.sql.jpa-and-spring-data.open-entity-manager-in-view): "to allow for lazy loading in web views. If you do not want this behavior, you should set `spring.jpa.open-in-view` to `false`"; left unset, Spring Boot warns at start-up: "spring.jpa.open-in-view is enabled by default. Therefore, database queries may be performed during view rendering. Explicitly configure spring.jpa.open-in-view to disable this warning" |
| Security filter scope | one `SecurityFilterChain` with `securityMatcher("/form", "/login", "/me")`; the phase-1 endpoints and `/world`, `/worlds` match no chain, so Spring Security's filter only parses the path, applies its `HttpFirewall` and passes the request on (no security filter, session or CSRF work). Not `WebSecurityCustomizer#ignoring()`, which Spring Security logs as "This is not recommended -- please use permitAll via HttpSecurity#authorizeHttpRequests instead" and which leaves the same pass-through; and not a catch-all chain with `permitAll()` (the reference's tip for protecting the whole application), which would run the full filter chain (headers, CSRF, security context, …) on the existing endpoints, against §2.3 of `docs/v3-spec.md` | [Multiple HttpSecurity Instances](https://docs.spring.io/spring-security/reference/servlet/configuration/java.html#_multiple_httpsecurity_instances): "we can employ multiple filter chains alongside the `securityMatcher` DSL method"; [Architecture](https://docs.spring.io/spring-security/reference/servlet/architecture.html#servlet-multi-securityfilterchain-figure): "Only the first `SecurityFilterChain` that matches is invoked"; [Favor `permitAll` over `ignoring`](https://docs.spring.io/spring-security/reference/servlet/authorization/authorize-http-requests.html#favor-permitall) |
| Pool | HikariCP, `spring.datasource.hikari.maximum-pool-size` = `DB_POOL_SIZE` (16); `minimum-idle` unset, so the pool is fixed at 16 | [Supported Connection Pools](https://docs.spring.io/spring-boot/reference/data/sql.html#data.sql.datasource.connection-pool): "We prefer HikariCP for its performance and concurrency"; [HikariCP `minimumIdle`](https://github.com/brettwooldridge/HikariCP#frequently-used): "we recommend *not* setting this value and instead allowing HikariCP to act as a *fixed size* connection pool" |
| Prepared statements | the PostgreSQL JDBC driver's default `prepareThreshold=5`: from the fifth execution of the same SQL on a connection it uses a named server-side prepared statement, kept in its per-connection cache (256 queries) across Hibernate's `prepareStatement` calls; no setting | [pgJDBC, Server Prepared Statements](https://jdbc.postgresql.org/documentation/server-prepare/): "when it reaches the prepareThreshold (default 5) the driver will switch to creating a named statement", "the driver is able to server-prepare statements automatically across connection.prepareStatement(...) calls" |
| Connection reset | none to configure: on return, HikariCP restores through JDBC only the properties the application changed (auto-commit, read-only, isolation, …); it sends no reset statement | HikariCP source: [`ProxyConnection.close`](https://github.com/brettwooldridge/HikariCP/blob/dev/src/main/java/com/zaxxer/hikari/pool/ProxyConnection.java), [`PoolBase.resetConnectionState`](https://github.com/brettwooldridge/HikariCP/blob/dev/src/main/java/com/zaxxer/hikari/pool/PoolBase.java) |
| Statement batching | off (Hibernate's default; `hibernate.jdbc.batch_size` unset). Hibernate's guide calls batching "an easy way to improve performance" when "a program executes many inserts, updates, or deletes against the same table in a single transaction", but in `/updates` the `AUTO` flush before each row's query sends the previous row's `UPDATE` on its own, so a batch would hold one statement | [Hibernate 7.4, Enabling statement batching](https://docs.hibernate.org/orm/7.4/introduction/html_single/#statement-batching) |
| Server, threads | embedded Tomcat with Spring Boot's defaults: `server.tomcat.threads.max` 200, `min-spare` 10, `max-keep-alive-requests` 100 (Tomcat closes a keep-alive connection after 100 requests); no other `server.*` property is set | [`server.tomcat.threads.max`](https://docs.spring.io/spring-boot/appendix/application-properties/index.html#application-properties.server.server.tomcat.threads.max), [`server.tomcat.max-keep-alive-requests`](https://docs.spring.io/spring-boot/appendix/application-properties/index.html#application-properties.server.server.tomcat.max-keep-alive-requests) |
| Virtual threads | off (the default); the reference makes them an opt-in and warns that "In some cases, applications can experience lower throughput because of 'Pinned Virtual Threads'" | [Virtual threads](https://docs.spring.io/spring-boot/reference/features/spring-application.html#features.spring-application.virtual-threads) |
| JVM flags | none, as in the reference Dockerfile (`ENTRYPOINT ["java", "-jar", "application.jar"]`): container ergonomics give G1 and a maximum heap of 25% of the 2 GiB limit; the optional AOT cache is not used (see above) | [Dockerfiles](https://docs.spring.io/spring-boot/reference/packaging/container-images/dockerfiles.html) |
| Templates | Thymeleaf cache on (Spring Boot's default) | |
| Caches | none (no response, query-result or second-level cache) | |

Database and application endpoints:

- `/db-single` and `GET /world/{id}` use `findById`. `/queries` and
  `/updates` read each row with a JPQL query (`WorldRepository.fetchById`),
  which always runs its `SELECT`: `/updates` is one transaction, in which
  `findById` would return a row its persistence context already holds without
  a `SELECT`, so a repeated id would not be read again.
- `/updates`: one `@Transactional` service method. The random ids are sorted
  (concurrent requests lock rows in the same order), each row is read, given
  a new value (different from the current one) and written by Hibernate's
  dirty checking: before the next query on `world` (flush mode `AUTO`) and at
  commit, one `UPDATE` per row. No JDBC batching is configured.
- `PUT /world/{id}`: the body is a record with `@NotNull @Min(1) @Max(10000)`
  checked before the handler; a `@Transactional` method loads the row, sets
  the field and the commit writes it. Jackson converts a JSON string to a
  number by default, so `spring.jackson.mapper.allow-coercion-of-scalars=false`
  makes `{"randomNumber": "5"}` a 400, as an integer field should.
- `GET /worlds`: `findByIdBetweenOrderByIdAsc(min, max, PageRequest)`
  returning a `List` (a `Page` would add a count query): one `SELECT` with
  `ORDER BY`, `OFFSET` and `FETCH FIRST`. `min > max` is checked by hand.
- `/fortunes`: `findAll()` (no `ORDER BY`), sorted with `String.compareTo`
  (UTF-16 code units, which is code-point order for these messages, none of
  which is outside the Basic Multilingual Plane), rendered by Thymeleaf with
  `th:text` (escaped).

Browser routes (`/form`, `/login`, `/me`), as the Spring Security reference
documents them ([CSRF](https://docs.spring.io/spring-security/reference/servlet/exploits/csrf.html),
[form login](https://docs.spring.io/spring-security/reference/servlet/authentication/passwords/form.html),
[session persistence](https://docs.spring.io/spring-security/reference/servlet/authentication/persistence.html)):

- CSRF: the default `HttpSessionCsrfTokenRepository` keeps one token per
  session; Thymeleaf's `th:action` adds it to the form as the XOR-masked
  `_csrf` field (Spring Security's `RequestDataValueProcessor`). Every masked
  value of the session's token is accepted, so a form page's cookie
  (`JSESSIONID`) and field stay valid for the whole round. A missing or wrong
  token is a 403.
- One deviation from the default: Spring Security 7.1.2's
  `XorCsrfTokenRequestAttributeHandler` throws an `IllegalArgumentException`
  (a 500) when a submitted token is valid Base64 of the right length but its
  unmasked bytes are not UTF-8, which a token changed in one character often
  is (`Utf8.decode` in `getTokenValue`). `MaskedCsrfTokenHandler` delegates
  every call to that handler and only turns the exception into "no token", so
  `CsrfFilter` answers the 403 it gives any wrong token. Valid tokens take
  exactly the default path.
- Login: `formLogin` processes `POST /login` (`username`, `password`,
  `_csrf`) with a `UserDetailsService` that reads `users` through
  `AccountRepository`. The password is checked by Spring Security's default
  `DelegatingPasswordEncoder` against `"{bcrypt}" + password_bcrypt` (the prefix
  that encoder reads). Success changes the session id and redirects (302) to
  `/me`; a wrong password redirects to `/login?error`.
- `/me` requires an authenticated session (otherwise 302 to `/login`, the form
  login entry point); the handler takes the principal (`AccountPrincipal`,
  the username and the id) from the session and reads the row with
  `findById` on every request.
- The session is Tomcat's in-memory `HttpSession` (one JVM process, so every
  request sees it), the default store of Spring Security's form login. No
  table is needed, so the folder has no `db.sql`. No login throttling exists
  in this setup.
- `PUT /world/{id}` is outside the security matcher, so it has no CSRF check.
- Global: Spring Security's servlet filter (`FilterChainProxy`) now runs for
  every request. For the other endpoints it only parses the request path
  (`ServletRequestPathFilter`), wraps the request in its `HttpFirewall` and
  finds that no filter chain matches the path; no security filter, session
  or CSRF check runs for them (see Production settings for why the chain is
  scoped this way).
