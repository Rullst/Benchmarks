# Contributing to the Rullst Benchmark Suite

Thank you for your interest in contributing! We welcome community additions to make this benchmark suite as comprehensive as possible. 

If you want to add a new web framework to the benchmark, please follow the guidelines below.

## 📋 How to Add a New Framework

To add a framework, you need to create a new folder with the framework's name in the root directory. Inside this folder, you must provide the application code and a `Dockerfile`.

### 1. The Application Code

Your application MUST implement the following four HTTP GET endpoints exactly as described:

- `/text`: Return a plain text response with the body `Hello World`.
- `/json`: Return a JSON response: `{"message": "Hello World"}`.
- `/db-single`: Fetch the record with `ID = 1` from the `world` table in the PostgreSQL database, and return it as JSON. The table schema is:
  ```sql
  CREATE TABLE world (
      id SERIAL PRIMARY KEY,
      random_number INT NOT NULL
  );
  ```
- `/html`: Return an HTML string (rendered via template or static string) with the content:
  ```html
  <!DOCTYPE html><html><head><title>Benchmark</title></head><body><h1>Hello World</h1></body></html>
  ```

### 2. Database Connection

Your application should read the database connection string from the `DATABASE_URL` environment variable.
Example format:
`postgres://benchmark:benchmark@db:5432/benchmark`

> **Note:** Ensure you configure a connection pool with sufficient size (e.g., 500 max open connections) to handle the massive load.

### 3. The Dockerfile

You must provide a `Dockerfile` that builds and runs your application.
- The application must expose port `8080` (or if it exposes another port, ensure it's documented, though `8080` or `3000` is standard in our scripts).
- Use a production-ready server/runtime configuration (e.g., compile with optimizations, use production flags, disable debug logging).
- Try to use Alpine or slim base images to keep the memory footprint low.

### 4. Update the Scripts & Docs

Once your folder is ready:
1. Open a Discussion or an Issue suggesting your framework.
2. If submitting a Pull Request, please add your framework's folder to the `run_benchmarks.sh` execution list.
3. Add your framework to the contenders list in `README.md` and `benchmarks_results.md`.

## 🐛 Reporting Bugs & Issues

If you notice that a specific framework is not configured optimally or is suffering from a bottleneck that doesn't represent its true capability, please open an Issue with the suggested code improvements!
