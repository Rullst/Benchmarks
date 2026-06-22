<div align="center">

# 🚀 Rullst Web Framework: Benchmark Suite

**The official performance, resilience, and load-testing suite for the Rullst Framework.**

[![Rust](https://img.shields.io/badge/Rust-1.85+-orange.svg?style=for-the-badge&logo=rust)](https://www.rust-lang.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg?style=for-the-badge&logo=docker)](https://www.docker.com/)
[![Benchmarks](https://img.shields.io/badge/Benchmarks-Bombardier%20%7C%20Criterion-success.svg?style=for-the-badge)]()

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
* **Load:** 500 concurrent connections for 30 seconds.
* **Endpoints:** `/json`

### 🧠 Tier 3: Resource Efficiency (Idle vs. Peak)
* **Goal:** Identify CPU and RAM utilization of "greedy" vs. "efficient" architectures.
* **Method:** Measure Docker stats during 0 traffic (Idle) vs. 200 concurrent connections (Peak).

### 🔥 Tier 4: Stress & Resilience (Memory Leak Detection)
* **Goal:** Ensure frameworks don't crash or leak memory under prolonged stress.
* **Load:** 1000 concurrent connections for a sustained 2 minutes.
* **Endpoints:** `/json`

### 💻 Hardware Specifications
*All benchmark results listed in this repository were run on the following environment to ensure consistency:*
* **CPU:** `[Enter CPU, e.g., Apple M3 Max / AMD Ryzen 9]`
* **RAM:** `[Enter RAM, e.g., 64GB Unified Memory]`
* **OS:** `[Enter OS, e.g., macOS Sonoma / Ubuntu 24.04]`
* **Docker Engine:** `[Enter Docker resources, e.g., 8 CPUs, 16GB RAM limit]`

### 🗄️ Database Architecture
All frameworks connect to a dedicated **PostgreSQL 15** container. 
* The database is initialized via the `db-init` scripts which pre-populate a table called `world` with thousands of random rows.
* Frameworks must fetch the `World` record with `ID = 1` for the `/db-single` endpoint. Connection pooling is strictly recommended.

---

## 🏆 The 25 Contenders (Targeting Latest Stable Versions - 2026)

We have updated our test suite to target the latest stable versions of all 25 frameworks:

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
| 10 | **Symfony** | PHP | `8.1.x` |
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
| 21 | **Rocket** | Rust | `0.5.x` |
| 22 | **Salvo** | Rust | `0.93.x` |
| 23 | **Warp** | Rust | `0.3.x` |
| 24 | **Next.js** | JS/TS (Node) | `15.x` |
| 25 | **Rullst** | Rust | `4.0.1` (Ours) |

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
