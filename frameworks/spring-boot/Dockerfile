# Build the executable jar with Maven. Maven has no lockfile: the Spring Boot
# parent pins every dependency and plugin version (see README.md).
FROM maven:3.10.0-eclipse-temurin-25-noble AS build
WORKDIR /src
COPY pom.xml ./
COPY src ./src
RUN mvn --batch-mode --no-transfer-progress package

# Extract the jar into layers, as in the Dockerfile of the Spring Boot
# reference documentation ("Packaging Spring Boot Applications > Container
# Images > Dockerfiles"), with Eclipse Temurin in place of Liberica.
FROM eclipse-temurin:25.0.5_8-jre-noble AS builder
WORKDIR /builder
COPY --from=build /src/target/app.jar application.jar
RUN java -Djarmode=tools -jar application.jar extract --layers --destination extracted
# Record the resolved versions of the main libraries for the results.
RUN find extracted -name '*.jar' -printf '%f\n' \
    | sed -nE 's/^(spring-boot|spring-webmvc|spring-data-jpa|hibernate-core|hibernate-validator|spring-security-web|HikariCP|thymeleaf|tomcat-embed-core|jackson-databind|postgresql)-([0-9][^-]*)\.jar$/\1 \2/p' \
    | sort > versions.txt \
    && echo "java ${JAVA_VERSION#jdk-}" >> versions.txt \
    && cat versions.txt

FROM eclipse-temurin:25.0.5_8-jre-noble
WORKDIR /application
COPY --from=builder /builder/extracted/dependencies/ ./
COPY --from=builder /builder/extracted/spring-boot-loader/ ./
COPY --from=builder /builder/extracted/snapshot-dependencies/ ./
COPY --from=builder /builder/extracted/application/ ./
COPY --from=builder /builder/versions.txt /bench/versions.txt
EXPOSE 8080
# No JVM flags: the JVM sizes its heap and picks its collector from the
# container's 2 vCPUs and 2 GiB (see README.md).
ENTRYPOINT ["java", "-jar", "application.jar"]
