<div align="center">

# 🚀 Rullst Web Framework: Benchmark Suite

**The official performance, resilience, and load-testing suite for the Rullst Framework.**

[![Rullst](https://img.shields.io/badge/Framework-Rullst-orange.svg)](#)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](#)
[![Rust](https://img.shields.io/badge/Rust-1.85%2B-black.svg)](#)

> 🌟 **[View the Interactive Web Dashboard](https://rullst.github.io/Benchmarks/)**
> 📊 **[View the Full Benchmark Results Table](./benchmarks_results.md)**

*Rullst is built to give you the extreme productivity of full-stack frameworks combined with the memory safety and blistering high throughput of Rust.*

</div>

---

## 🎯 What is this?

This repository contains a **comprehensive 4-tier benchmark suite** designed to rigorously evaluate the performance, resilience, and resource efficiency of **25 modern web frameworks** across multiple languages. 

We don't just guess; we measure. 📊

---

## 🧪 Benchmark Methodology (4-Tier Architecture)

To simulate different real-world scenarios, our testing approach is divided into four robust tiers:

### 🌍 Tier 1: Fast Load (Baseline Performance)
* **Goal:** Establish a baseline for raw Requests Per Second (RPS) and latency.
* **Load:** 125 concurrent connections for 10 seconds.
* **Endpoints:** `/text`, `/json`, `/db-single`, `/html`

### ⚡ Tier 2: Concurrency & Latency (High Traffic)
* **Goal:** Evaluate behavior under sudden traffic spikes and measure P99 latency.
* **Load:** 300 concurrent connections for 30 seconds.
* **Endpoints:** `/json`

### 🧠 Tier 3: Resource Efficiency (Idle vs. Peak)
* **Goal:** Identify CPU and RAM utilization of "greedy" vs. "efficient" architectures.
* **Method:** Measure Docker stats during 0 traffic (Idle) vs. 200 concurrent connections (Peak).

### 🔥 Tier 4: Stress & Resilience (Memory Leak Detection)
* **Goal:** Ensure frameworks don't crash or leak memory under prolonged stress.
* **Load:** 500 concurrent connections for a sustained 2 minutes.
* **Endpoints:** `/json`

### 🏅 The Efficiency Ranking Score (RPS/MB)
Our official ranking is determined by the **Efficiency Score**, which measures how many requests a framework can handle per megabyte of memory it consumes.
* **Formula:** `Efficiency = JSON RPS (Tier 1) / Peak RAM in MB (Tier 3)`
* **Example:** A framework handling 100,000 RPS with 20MB RAM scores `5,000`. A framework handling 100,000 RPS with 200MB RAM scores `500`.
* **The Disqualification Penalty:** Any framework that drops connections, crashes, or returns `timeout` errors during the **Tier 4 Stress Test** is automatically disqualified and receives **0 Points**. Speed is irrelevant if the server collapses under pressure!

### 💻 Minimum Hardware Requirements
To run these benchmarks locally without skewing the results due to resource starvation (especially during the 500-connection Tier 4 tests), we recommend the following minimum specifications:
* **CPU:** 4 Cores / 8 Threads (8+ Cores recommended)
* **RAM:** 8GB Minimum (16GB+ recommended)
* **OS:** Linux, macOS, or Windows (WSL2)
* **Docker Engine:** Ensure Docker is allocated at least 4 CPUs and 8GB of RAM.

### 📊 Official Tested Hardware
*All benchmark results listed in this repository were run on the following environment to ensure consistency:*
* **CPU:** `AMD Ryzen 7 5700U (8 Cores / 16 Threads)`
* **RAM:** `8GB`
* **OS:** `Windows 11 (Docker with WSL2)`

### 🗄️ Database Architecture
All frameworks connect to a dedicated **PostgreSQL 15** container. 
* The database is initialized via the `db-init` scripts which pre-populate a table called `world` with thousands of random rows.
* Frameworks must fetch the `World` record with `ID = 1` for the `/db-single` endpoint. Connection pooling is strictly recommended.

---

## 🏆 The 23 Contenders (Targeting Latest Stable Versions - 2026)

We have updated our test suite to target the latest stable versions of all 23 frameworks:

| # | Framework | Language / Runtime | Targeted Version |
|---|---|---|---|
| 1 | **Express** | JS/TS (Node) | `5.1.x` |
| 2 | **Fastify** | JS/TS (Node) | `5.8.x` |
| 3 | **NestJS** | JS/TS (Node) | `11.1.x` |
| 4 | **Hono** | JS/TS | `4.12.x` |
| 5 | **Go-Fiber** | Go | `3.0.x` |
| 6 | **Go-Gin** | Go | `1.11.x` |
| 7 | **Django** | Python | `6.0.x` |
| 8 | **FastAPI** | Python | `0.138.x` |
| 9 | **Laravel** | PHP | `13.x` |
| 10 | **Symfony** | PHP | `7.4.x` |
| 11 | **Ruby on Rails** | Ruby | `7.2.x` |
| 12 | **Phoenix** | Elixir | `1.8.x` |
| 13 | **Quarkus** | Java | `3.36.x` |
| 14 | **Spring Boot** | Java | `4.0.x` |
| 15 | **ASP.NET Core** | C# (.NET) | `10.0.x` |
| 16 | **Actix Web** | Rust | `4.13.x` |
| 17 | **Axum** | Rust | `0.8.x` |
| 18 | **Dioxus** | Rust | `0.7.x` |
| 19 | **Leptos** | Rust | `0.7.x` |
| 20 | **Poem** | Rust | `3.x` |
| 21 | **Salvo** | Rust | `0.93.x` |
| 22 | **Next.js** | JS/TS (Node) | `15.x` |
| 23 | **Rullst** | Rust | `4.0.1` (Ours) |

---

## 🏅 Official Efficiency Ranking

| 🏆 Rank | Framework | Language | Efficiency (RPS/MB) | JSON RPS | DB Single RPS | Avg Latency | Peak RAM | Status |
|:---:|---|---|---:|---:|---:|---:|---:|:---:|
| 🥇 1st | Actix-Web | Rust | **6.778** | 128.654,31 | 12.366,9 | 2.34ms | 18.98MiB | ✅ Passed |
| 🥈 2nd | Axum | Rust | **4.580** | 100.620,33 | 18.033,16 | 2.61ms | 21.97MiB | ✅ Passed |
| 🥉 3rd | Poem | Rust | **4.346** | 98.795,48 | 12.405,22 | 2.68ms | 22.73MiB | ✅ Passed |
| 4 | **Rullst** 👑 | Rust | **4.344** | 90.485,67 | 16.186,7 | 3.14ms | 20.83MiB | ✅ Passed |
| 5 | Salvo | Rust | **4.141** | 92.218,37 | 7.465,66 | 2.96ms | 22.27MiB | ✅ Passed |
| 6 | Go-Fiber | Go | **4.032** | 99.803,89 | 16.026,64 | 2.68ms | 24.75MiB | ✅ Passed |
| 7 | Dioxus | Rust | **3.448** | 87.638,05 | 9.431,99 | 2.79ms | 25.42MiB | ✅ Passed |
| 8 | Leptos | Rust | **3.024** | 77.135,01 | 8.009 | 2.94ms | 25.51MiB | ✅ Passed |
| 9 | Go-Gin | Go | **2.898** | 70.219,4 | 13.627,19 | 4.14ms | 24.23MiB | ✅ Passed |
| 10 | ASP.NET Core | C# | **718** | 75.723,47 | 11.181,52 | 3.63ms | 105.5MiB | ✅ Passed |
| 11 | Phoenix | Elixir | **73** | 16.243,87 | 2.400,09 | 15.82ms | 223.4MiB | ✅ Passed |
| 12 | Quarkus | Java | **62** | 27.789,39 | 2.867,81 | 4.49ms | 449.6MiB | ✅ Passed |
| 13 | FastAPI | Python | **27** | 7.568,21 | 2,49 | 48.12ms | 282MiB | ✅ Passed |
| 14 | Spring Boot | Java | **15** | 7.648,31 | 260,65 | 11.98ms | 508.4MiB | ✅ Passed |
| 15 | Ruby on Rails | Ruby | **3** | 298,56 | 144,6 | 0.99s | 100.3MiB | ✅ Passed |
| 16 | Django | Python | **0** | 4.733,45 | 3,82 | 1.26m | 139.3MiB | ❌ Failed |
| 17 | Express | Node.js | **0** | 3.804,97 | 1.051,43 | 86.05ms | 101.1MiB | ❌ Failed |
| 18 | Fastify | Node.js | **0** | 11.544,78 | 1.364,58 | 26.11ms | 92.84MiB | ❌ Failed |
| 19 | Hono | TypeScript | **0** | 7.959,06 | 898,71 | 42.63ms | 88.43MiB | ❌ Failed |
| 20 | Laravel | PHP | **0** | 97.957,06 | 82.542,81 | 3.37ms | 0B | ❌ Failed |
| 21 | NestJS | Node.js | **0** | 2.855,24 | 857,72 | 109.53ms | 120.2MiB | ❌ Failed |
| 22 | Next.js | TypeScript | **0** | 510,52 | 358,1 | 677.85ms | 129.8MiB | ❌ Failed |
| 23 | Symfony | PHP | **0** | 102.008,3 | 102.971,02 | 3.25ms | 70.17MiB | ❌ Failed |

---

## 🛠️ Prerequisites

Before launching the rockets, ensure your environment is ready:

- 🐳 **Docker** & **Docker Compose** *(Crucial for containerized, isolated environments)*
- 🦀 **Rust (v1.85+)** *(Required if running internal Rust micro-benchmarks)*
- 🐍 **Python (v3.x)** *(Used to parse results and build tables)*

---

## 🚀 Running the Benchmarks

To ensure pinpoint accuracy, our bash scripts orchestrate everything automatically (building, starting, benchmarking, and tearing down sequentially).

**🖥️ Execution (Linux / macOS / WSL / Git Bash):**
```bash
chmod +x run_benchmarks.sh
./run_benchmarks.sh
```

*(Note: You can also explore `run_batch.sh` to test specific batches of frameworks).*

**📈 Output:** 
The raw results are saved under `results/` and automatically compiled into a neat comparative markdown table (e.g., `benchmarks_results.md`).

---

## 🤝 Contributing

Want to include a framework in this list or improve a script? Feel free to leave a comment in the **Discussions** or open an **Issue** in this repository! For detailed instructions on how to add your own framework, please check our [CONTRIBUTING.md](CONTRIBUTING.md).

## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

<div align="center">
  <i>"Speed is a feature. Developer Experience is a mandate."</i>
  <br><br>
  <b>— The Rullst Team</b>
</div>
