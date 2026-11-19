"""wrk, the suite's load generator, returning loadgen.run_load's metrics dict.

wrk (C, epoll, LuaJIT) sends either one fixed request (static mode: no Lua
`request` function, wrk builds the request once) or, for a Workload with
several requests, the prebuilt requests in a shuffled cycle (dynamic mode:
the Lua `request` function returns the next prebuilt string, so no request
is formatted while measuring). A Lua `done` function prints the summary as
one `WRK_JSON {...}` line.

What the results must state:
- wrk itself counts a response as an error only when its status is 400 or
  above (3xx counts as success); count_statuses=True adds a Lua `response`
  hook that counts every status class exactly, at a client CPU cost (the
  phase-2 workloads use it);
- `-t T -c C` opens C // T connections per thread (124 for 125 on 2 threads);
  `connections_open` records the real number;
- a request slower than the timeout is counted in `timeouts` and, if it
  completes later, also in the requests.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from loadgen_process import error_metrics, measure
from system import format_cpu_list
from workload import Workload, static

FORBIDDEN = ("\t", "\n", "\r", "\x1e", "\x1f")

LUA_COMMON = r"""
-- Written by bench/loadgen_wrk.py.
local thread_count = 0
local threads = {}
function setup(thread)
  thread:set("tid", thread_count)
  thread_count = thread_count + 1
  threads[thread_count] = thread
end

local function split(s, sep)
  local out, start = {}, 1
  while true do
    local a, b = string.find(s, sep, start, true)
    if not a then out[#out + 1] = string.sub(s, start); return out end
    out[#out + 1] = string.sub(s, start, a - 1)
    start = b + 1
  end
end

local function parse(line)
  local f = split(line, "\t")
  local headers = {}
  if f[3] ~= "" then
    for _, h in ipairs(split(f[3], "\31")) do
      local kv = split(h, "\30")
      headers[kv[1]] = kv[2]
    end
  end
  return f[1], f[2], headers, (f[4] ~= "" and f[4] or nil)
end

function done(summary, latency, requests)
  local e = summary.errors
  -- Status classes counted by the optional response() hook (-1: not counted).
  local classes = {-1, -1, -1, -1, -1}
  for _, t in ipairs(threads) do
    for k = 1, 5 do
      local n = t:get("s" .. k .. "xx")
      if n then classes[k] = math.max(classes[k], 0) + n end
    end
  end
  io.write(string.format(
    'WRK_JSON {"duration_us":%d,"requests":%d,"bytes":%d,"connect":%d,"read":%d,"write":%d,' ..
    '"status":%d,"timeout":%d,"mean_us":%.3f,"max_us":%d,"p50_us":%d,"p90_us":%d,"p99_us":%d,' ..
    '"s1xx":%d,"s2xx":%d,"s3xx":%d,"s4xx":%d,"s5xx":%d}\n',
    summary.duration, summary.requests, summary.bytes, e.connect, e.read, e.write, e.status,
    e.timeout, latency.mean, latency.max, latency:percentile(50), latency:percentile(90),
    latency:percentile(99), classes[1], classes[2], classes[3], classes[4], classes[5]))
end
"""

LUA_STATIC = r"""
function init(args)
  for line in io.lines(args[1]) do
    local method, path, headers, body = parse(line)
    wrk.method = method
    wrk.path = path
    for k, v in pairs(headers) do wrk.headers[k] = v end
    wrk.body = body
  end
end
"""

# Counts every response by status class. wrk then parses each response's
# headers and body into Lua, which costs client CPU (measured in the
# experiment, docs/v3-spec.md section 7).
LUA_STATUS = r"""
s1xx, s2xx, s3xx, s4xx, s5xx = 0, 0, 0, 0, 0
function response(status, headers, body)
  if status < 200 then s1xx = s1xx + 1
  elseif status < 300 then s2xx = s2xx + 1
  elseif status < 400 then s3xx = s3xx + 1
  elseif status < 500 then s4xx = s4xx + 1
  else s5xx = s5xx + 1 end
end
"""

LUA_DYNAMIC = r"""
local reqs, n, i = {}, 0, 0
function init(args)
  for line in io.lines(args[1]) do
    local method, path, headers, body = parse(line)
    if not headers["Host"] then headers["Host"] = wrk.headers["Host"] end
    reqs[#reqs + 1] = wrk.format(method, path, headers, body)
  end
  n = #reqs
  -- Threads start at different points of the shuffled cycle.
  i = (tid * 7919) % n
end

function request()
  i = i + 1
  if i > n then i = 1 end
  return reqs[i]
end
"""


def write_files(workload: Workload, workdir: Path, count_statuses: bool = False) -> tuple[Path, Path]:
    """The Lua script and its request file for a workload."""
    workdir.mkdir(parents=True, exist_ok=True)
    lines = []
    for r in workload.requests:
        body = r.body.decode("utf-8")
        headers = "\x1f".join(f"{k}\x1e{v}" for k, v in r.headers)
        for value in (r.method, r.path, body, *(part for pair in r.headers for part in pair)):
            if any(ch in value for ch in FORBIDDEN):
                raise ValueError(f"request field {value[:60]!r} contains a tab, newline or separator")
        lines.append("\t".join((r.method, r.path, headers, body)))
    requests = workdir / "requests.tsv"
    requests.write_text("\n".join(lines) + "\n", encoding="utf-8")
    script = workdir / ("static.lua" if workload.static else "dynamic.lua")
    script.write_text(LUA_COMMON + (LUA_STATIC if workload.static else LUA_DYNAMIC)
                      + (LUA_STATUS if count_statuses else ""), encoding="utf-8")
    return script, requests


def parse_output(stdout: str) -> dict:
    line = next(l for l in reversed(stdout.splitlines()) if l.startswith("WRK_JSON "))
    raw = json.loads(line[len("WRK_JSON "):])
    duration = raw["duration_us"] / 1e6
    transport = raw["connect"] + raw["read"] + raw["write"] + raw["timeout"]
    kinds = {k: raw[k] for k in ("connect", "read", "write", "timeout", "status") if raw[k]}
    counted = raw.get("s2xx", -1) >= 0
    if counted:  # exact classes from the response() hook
        ok = raw["s2xx"]
        status_errors = raw["s1xx"] + raw["s3xx"] + raw["s4xx"] + raw["s5xx"]
    else:  # wrk's own count: only statuses of 400 and above are errors
        status_errors = raw["status"]
        ok = raw["requests"] - status_errors

    def ms(us) -> float:
        return round(us / 1000.0, 3)

    metrics = error_metrics(
        ok=ok, non_2xx=status_errors, transport_errors=transport,
        timeouts=raw["timeout"], duration=duration, error_kinds=kinds,
        latency_ms={"mean": ms(raw["mean_us"]), "p50": ms(raw["p50_us"]), "p90": ms(raw["p90_us"]),
                    "p99": ms(raw["p99_us"]), "max": ms(raw["max_us"])})
    metrics["bytes"] = raw["bytes"]
    if counted:
        metrics["status_classes"] = {f"{k}xx": raw[f"s{k}xx"] for k in range(1, 6)}
    return metrics


def build_command(binary: Path, url: str, script: Path, requests: Path, *, connections: int,
                  duration_s: int, threads: int, timeout_s: int, client_cpus: list[int]) -> list[str]:
    return ["taskset", "-c", format_cpu_list(client_cpus), str(binary), "-t", str(threads),
            "-c", str(connections), "-d", f"{duration_s}s", "--timeout", f"{timeout_s}s",
            "-s", str(script), url, "--", str(requests)]


def run_load(binary: Path, url: str, *, connections: int, duration_s: int, config: dict,
             client_cpus: list[int], server=None, database=None, db_cpus: list[int] | None = None,
             workload: Workload | None = None, tool_config: dict | None = None,
             workdir: Path | None = None, count_statuses: bool = False) -> dict:
    """loadgen.run_load with wrk. Without a workload, `url` is fetched with GET.

    With a workload, `url` is the server's base URL (scheme, host and port)
    and the workload supplies the paths.
    """
    tool_config = tool_config or {"timeout_s": 5, "saturation_threshold": 0.9, "version": "?"}
    parts = urlsplit(url)
    base = f"{parts.scheme}://{parts.netloc}/"
    if workload is None:
        workload = static(parts.path + (f"?{parts.query}" if parts.query else "") or "/")
    workdir = workdir or Path(tempfile.gettempdir()) / "bench-wrk"
    script, requests = write_files(workload, workdir, count_statuses)
    threads = max(1, min(len(client_cpus), connections))
    cmd = build_command(binary, base, script, requests, connections=connections, duration_s=duration_s,
                        threads=threads, timeout_s=tool_config["timeout_s"], client_cpus=client_cpus)
    metrics = measure(cmd, parse_output, tool="wrk", connections=connections, duration_s=duration_s,
                      config=config, client_cpus=client_cpus,
                      saturation_threshold=tool_config["saturation_threshold"], server=server,
                      database=database, db_cpus=db_cpus)
    metrics["connections_open"] = (connections // threads) * threads
    metrics["load_generator"] = f"wrk {tool_config['version']}"
    metrics["workload"] = {"label": workload.label, "requests": len(workload.requests),
                           "mode": "static" if workload.static else "dynamic",
                           "count_statuses": count_statuses}
    return metrics
