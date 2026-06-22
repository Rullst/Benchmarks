# 🏆 Rullst Benchmarks 2026: The Ultimate Results

> **Last Updated:** June 22, 2026
> **Interactive Dashboard:** [View Web Dashboard](https://your-github-username.github.io/Benchmarks/)

Welcome to the consolidated, high-performance benchmarking results. We pit **23 modern web frameworks** against each other in a rigorous, containerized 4-tier stress test.

## 🎯 The Ultimate Ranking (By Efficiency)

In modern cloud environments, pure speed means nothing if it costs thousands of dollars in RAM. The ranking below is sorted by the **Efficiency Score** (JSON Requests Per Second divided by Peak RAM usage). 

*The higher the score, the more performant and cheaper the framework is to host.*

| 🏆 Rank | Framework | Language | Efficiency (RPS/MB) | JSON RPS | DB Single RPS | Avg Latency | Peak RAM | Status |
|:---:|---|---|---:|---:|---:|---:|---:|:---:|
| 🥇 1st | Laravel | PHP | **91.515** | 91.514,97 | 90.775,91 | 3.13ms | 0B | ❌ Failed |
| 🥈 2nd | Axum | Rust | **56.230** | 89.406 | 101.950,26 | 2.95ms | 1.59MiB | ✅ Passed |
| 🥉 3rd | Actix-Web | Rust | **33.241** | 79.844,83 | 77.687,94 | 3.76ms | 2.402MiB | ✅ Passed |
| 4 | Poem | Rust | **4.654** | 107.099,23 | 12.711,57 | 2.75ms | 23.01MiB | ✅ Passed |
| 5 | Salvo | Rust | **4.497** | 99.028,92 | 8.296,87 | 2.92ms | 22.02MiB | ✅ Passed |
| 6 | Go-Fiber | Go | **4.407** | 102.904,17 | 16.021,92 | 2.66ms | 23.35MiB | ✅ Passed |
| 7 | **Rullst** 👑 | Rust | **3.921** | 79.602,8 | 14.324,03 | 3.37ms | 20.3MiB | ✅ Passed |
| 8 | Leptos | Rust | **3.794** | 99.700,15 | 10.316,37 | 2.57ms | 26.28MiB | ✅ Passed |
| 9 | Dioxus | Rust | **3.452** | 88.542,41 | 9.523,73 | 2.70ms | 25.65MiB | ✅ Passed |
| 10 | Go-Gin | Go | **2.863** | 69.575,28 | 21.474,06 | 3.73ms | 24.3MiB | ✅ Passed |
| 11 | Symfony | PHP | **1.240** | 82.987,04 | 88.186,31 | 3.80ms | 66.91MiB | ✅ Passed |
| 12 | Django | Python | **859** | 106.248,37 | 103.591,46 | 2.63ms | 123.7MiB | ✅ Passed |
| 13 | ASP.NET Core | C# | **706** | 81.610,33 | 11.908,18 | 3.44ms | 115.6MiB | ✅ Passed |
| 14 | Quarkus | Java | **474** | 99.240,5 | 97.228,41 | 2.99ms | 209.4MiB | ✅ Passed |
| 15 | FastAPI | Python | **449** | 107.841,78 | 100.160,49 | 3.06ms | 240.4MiB | ✅ Passed |
| 16 | Spring Boot | Java | **327** | 99.507,43 | 96.305,4 | 2.96ms | 304.2MiB | ✅ Passed |
| 17 | Fastify | Node.js | **96** | 8.642,38 | 755,57 | 32.28ms | 89.92MiB | ✅ Passed |
| 18 | Phoenix | Elixir | **67** | 14.801,11 | 2.480,69 | 15.84ms | 220MiB | ✅ Passed |
| 19 | Hono | TypeScript | **48** | 4.202,99 | 557,18 | 63.43ms | 87.75MiB | ✅ Passed |
| 20 | Express | Node.js | **23** | 2.216,46 | 590,25 | 140.71ms | 97.55MiB | ✅ Passed |
| 21 | NestJS | Node.js | **17** | 2.461,05 | 689,01 | 121.79ms | 146.7MiB | ✅ Passed |
| 22 | Next.js | TypeScript | **4** | 505,66 | 335,9 | 719.64ms | 124.1MiB | ✅ Passed |
| 23 | Ruby on Rails | Ruby | **3** | 286,87 | 134,44 | 1.00s | 100.1MiB | ✅ Passed |


---

## 📈 Methodology Explained

If you want to understand the Tiers (Tier 1 to 4) and how we measure database throughput, latency, and idle resources, please refer to the detailed methodology in our [README.md](./README.md).

*Generated automatically by the Rullst Benchmark Suite.*
