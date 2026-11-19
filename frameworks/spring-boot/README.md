# Spring Boot

| | |
| --- | --- |
| Version | Spring Boot 4.1.2, which pins Spring Framework 7.0, Spring Data JPA, Hibernate 7.4, Tomcat 11.0, Thymeleaf 3.1, HikariCP 7.0 and the PostgreSQL JDBC driver 42.7 (the resolved jars are listed in `/bench/versions.txt` in the image) |
| Build | `mvn package` with Maven 3.10.0 on Eclipse Temurin 25; the executable jar is extracted into layers with `java -Djarmode=tools -jar application.jar extract --layers` and started with `java -jar application.jar` |
| Server | Spring MVC on embedded Tomcat, the default of `spring-boot-starter-webmvc`, with Tomcat's default request thread pool (up to 200 threads) |
| JVM | Eclipse Temurin 25.0.5 JRE (Java 25 LTS) with no JVM flags: the JVM sizes itself from the container (2 vCPUs, 2 GiB), so it uses G1 and a maximum heap of 25% of the memory limit (512 MiB) |
| Database | Spring Data JPA (Hibernate) entities `World`, `Fortune` and `Account` (`users`); HikariCP `maximum-pool-size` = `DB_POOL_SIZE` (16); `ddl-auto=none`; `Application.main` translates `DATABASE_URL` into the JDBC URL and credentials |
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
- Open EntityManager in View stays on (Spring Boot's default). The
  documentation only says to set `spring.jpa.open-in-view=false` "if you do not
  want this behavior" and does not recommend it for production; the property
  is set to `true` explicitly to document the choice and silence the start-up
  warning.
- Everything else is Spring Boot's default: no virtual threads
  (`spring.threads.virtual.enabled` is off by default), no Hibernate
  second-level or query cache, no extra filters.

Database and application endpoints:

- `/db-single` and `GET /world/{id}` use `findById`. `/queries` and
  `/updates` read each row with a JPQL query (`WorldRepository.fetchById`),
  because `findById` returns a row the request's persistence context already
  holds (open-in-view) without a `SELECT`, so a repeated id would not be read.
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
  every request. For the other endpoints it only wraps the request in its
  `HttpFirewall` and finds that no filter chain matches the path; no
  security filter, session or CSRF check runs for them.
