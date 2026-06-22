# Web Frameworks Benchmark 2026 (4-Tier Architecture)

## Overview

This repository contains a comprehensive, robust, and highly standardized 4-tier benchmark suite designed to evaluate the performance, resilience, and resource efficiency of **25 modern web frameworks** across multiple languages (Rust, Go, Node.js, Python, PHP, Ruby, Java, and Elixir). 

The ultimate goal of this benchmark is to objectively measure how the **Rullst** framework (Rust) performs against industry standards in both raw speed and memory footprint.

## Methodology

To ensure fairness, all frameworks are containerized using `docker-compose` and connected to a dedicated PostgreSQL 15 instance. Network latency is minimized by using host networking for the load generation tool (`bombardier`).

The benchmark is divided into four distinct "Tiers" to simulate different real-world scenarios:

### Tier 1: Fast Load (Baseline Performance)
- **Goal:** Establish a baseline for raw Requests Per Second (RPS) and basic latency.
- **Load:** 125 concurrent connections for 10 seconds.
- **Endpoints Tested:** 
  - `/text` (Plain text response)
  - `/json` (JSON serialization)
  - `/db-single` (Single database query fetching one record)
  - `/html` (HTML template rendering)

### Tier 2: Concurrency & Latency (High Traffic)
- **Goal:** Evaluate how the framework handles sudden traffic spikes and measure the P99 latency (the time it takes for the slowest 1% of requests).
- **Load:** 300 concurrent connections for 30 seconds.
- **Endpoints Tested:** `/json`

### Tier 3: Resource Efficiency (Idle vs. Peak)
- **Goal:** Measure CPU and RAM utilization to identify "greedy" vs. "efficient" architectures.
- **Methodology:** 
  - **Idle State:** Captured using `docker stats` after the framework is fully booted but receiving 0 traffic.
  - **Peak State:** Captured while sustaining a load of 200 concurrent connections for 30 seconds.

### Tier 4: Stress & Resilience (Memory Leak Detection)
- **Goal:** Ensure the framework does not crash or leak memory under prolonged stress.
- **Load:** 500 concurrent connections for a sustained duration of 2 minutes (Marathon Test).
- **Endpoints Tested:** `/json`

### Official Tested Hardware
*The tests were executed on the following isolated environment:*
- **Processor (CPU):** `AMD Ryzen 7 5700U (8 Cores / 16 Threads)`
- **Memory (RAM):** `8GB`
- **Operating System:** `Windows 11 (Docker with WSL2)`

---

## Tested Frameworks (Total: 25)

The frameworks are grouped into batches to manage system resources during testing:

- **Batch 1 (JS/TS & Go):** Express, Fastify, NestJS, Hono, Go-Fiber, Go-Gin
- **Batch 2 (Java, Ruby, Python, PHP, Elixir):** Django, FastAPI, Laravel, Symfony, Rails, Phoenix, Quarkus, Spring Boot, ASP.NET Core
- **Batch 3 (Rust Core):** Actix, Axum, Dioxus, Leptos
- **Batch 4 (Rust Extras & Rullst):** Poem, Rocket, Salvo, Warp, **Rullst**

---

## Benchmark Results

> **Date:** June 21, 2026

### Batch 1: Fast Interpreted & Compiled (JS/TS & Go)
*Status: ✅ Completed*

| Framework | Version | Tier 1 (JSON RPS) | Tier 1 (DB RPS) | Tier 2 (Avg Latency) | Tier 3 (Idle RAM) | Tier 3 (Peak RAM) | Tier 4 (Status) |
|-----------|---------|-------------------|-----------------|----------------------|-------------------|-------------------|-----------------|
| Express   | 5.1.0   | 2216.46           | 590.25          | 140.71ms             | 44.79MiB          | 97.55MiB          | Passed          |
| Fastify   | 5.8.0   | 8642.38           | 755.57          | 32.28ms              | 85.57MiB          | 89.92MiB          | Passed          |
| NestJS    | latest  | 2461.05           | 689.01          | 121.79ms             | 145.5MiB          | 146.7MiB          | Passed          |
| Hono      | 4.12.0  | 4202.99           | 557.18          | 63.43ms              | 82.17MiB          | 87.75MiB          | Passed          |
| Go-Fiber  | v3.0.0  | 102904.17         | 16021.92        | 2.66ms               | 21.56MiB          | 23.35MiB          | Passed          |
| Go-Gin    | v1.12.0 | 69575.28          | 21474.06        | 3.73ms               | 23.6MiB           | 24.3MiB           | Passed          |

### Batch 3 & 4: Rust Ecosystem
*Status: ✅ Completed (Batch 3)*

| Framework | Version | Tier 1 (JSON RPS) | Tier 1 (DB RPS) | Tier 2 (Avg Latency) | Tier 3 (Idle RAM) | Tier 3 (Peak RAM) | Tier 4 (Status) |
|-----------|---------|-------------------|-----------------|----------------------|-------------------|-------------------|-----------------|
| Actix-Web | 4.x | 79844.83 | 77687.94 | 3.76ms | 2.402MiB | 2.402MiB | Passed |
| Axum | 0.8.x | 89406.00 | 101950.26 | 2.95ms | 1.59MiB | 1.59MiB | Passed |
| Dioxus | 0.7.x | 88542.41 | 9523.73 | 2.70ms | 20.48MiB | 25.65MiB | Passed |
| Leptos | 0.7.x | 99700.15 | 10316.37 | 2.57ms | 22.09MiB | 26.28MiB | Passed |
| Poem | 3.x | 107099.23 | 12711.57 | 2.75ms | 17.54MiB | 23.01MiB | Passed |
| Salvo | 0.93.x | 99028.92 | 8296.87 | 2.92ms | 16.53MiB | 22.02MiB | Passed |

### Batch 2: Enterprise & Scripting (Java, C#, Python, PHP, Ruby, Elixir)
*Status: ✅ Completed*

| Framework | Version | Tier 1 (JSON RPS) | Tier 1 (DB RPS) | Tier 2 (Avg Latency) | Tier 3 (Idle RAM) | Tier 3 (Peak RAM) | Tier 4 (Status) |
|-----------|---------|-------------------|-----------------|----------------------|-------------------|-------------------|-----------------|
| Django | 6.0.0 | 106248.37 | 103591.46 | 2.63ms | 123.7MiB | 123.7MiB | Passed |
| FastAPI | 0.138.0 | 107841.78 | 100160.49 | 3.06ms | 239.2MiB | 240.4MiB | Passed |
| Laravel | 13.x | 91514.97 | 90775.91 | 3.13ms | 0B | 0B | Failed |
| Symfony | 7.4.x | 82987.04 | 88186.31 | 3.80ms | 66.91MiB | 66.91MiB | Passed |
| Ruby on Rails | 7.2.x | 286.87 | 134.44 | 1.00s | 97.26MiB | 100.1MiB | Passed |
| Phoenix | 1.8.x | 14801.11 | 2480.69 | 15.84ms | 217.4MiB | 220MiB | Passed |
| Quarkus | 3.36.x | 99240.50 | 97228.41 | 2.99ms | 209.4MiB | 209.4MiB | Passed |
| Spring Boot | 4.0.x | 99507.43 | 96305.40 | 2.96ms | 303.6MiB | 304.2MiB | Passed |
| ASP.NET Core | 10.0.x | 81610.33 | 11908.18 | 3.44ms | 110.2MiB | 115.6MiB | Passed |

### Batch 4: Fullstack & SSR (Next.js)
*Status: ✅ Completed*

| Framework | Version | Tier 1 (JSON RPS) | Tier 1 (DB RPS) | Tier 2 (Avg Latency) | Tier 3 (Idle RAM) | Tier 3 (Peak RAM) | Tier 4 (Status) |
|-----------|---------|-------------------|-----------------|----------------------|-------------------|-------------------|-----------------|
| Next.js | 15.5.x | 505.66 | 335.90 | 719.64ms | 120.9MiB | 124.1MiB | Passed |

---
*Generated by the automated Rullst benchmarking suite.*
