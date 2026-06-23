# 🏆 Rullst Benchmarks 2026: The Ultimate Results

> **Last Updated:** June 22, 2026
> **Interactive Dashboard:** [View Web Dashboard](https://rullst.github.io/Benchmarks/)

Welcome to the consolidated, high-performance benchmarking results. We pit **23 modern web frameworks** against each other in a rigorous, containerized 4-tier stress test.

## 🎯 The Ultimate Ranking (By Efficiency)

In modern cloud environments, pure speed means nothing if it costs thousands of dollars in RAM. The ranking below is sorted by the **Efficiency Score** (JSON Requests Per Second divided by Peak RAM usage). 

*The higher the score, the more performant and cheaper the framework is to host.*

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


> [!WARNING]
> **Why is my favorite framework ranked last with 0 points?**
> If a framework has ❌ Failed status, it means it failed the **Tier 4 Stress Test** (500 concurrent connections for 2 minutes) by returning `connection refused` or `timeout` errors. 
> Some frameworks (like synchronous Python or PHP setups) may also experience catastrophic latency degradation (measured in minutes instead of milliseconds) before eventually timing out.
> Frameworks that drop connections or crash under extreme concurrency are automatically disqualified from the efficiency ranking to ensure we only reward truly resilient architectures.

---

## 📈 Methodology Explained

If you want to understand the Tiers (Tier 1 to 4) and how we measure database throughput, latency, and idle resources, please refer to the detailed methodology in our [README.md](./README.md).

*Generated automatically by the Rullst Benchmark Suite.*
