"""Docker helpers: image builds, the PostgreSQL container, servers and their cgroups."""

from __future__ import annotations

import io
import json
import os
import re
import subprocess
import tarfile
import time
import urllib.request
from pathlib import Path

from common import BENCH, FRAMEWORKS, READY_POLL_S, BenchError, log, run
from system import format_cpu_list

DB_CONTAINER = "bench-db"
MIB = 1024 * 1024


def image_tag(slug: str) -> str:
    return f"bench/{slug}:local"


def base_images(dockerfile: Path) -> list[str]:
    """Images a Dockerfile pulls: FROM lines and COPY --from=<image>, not stages or scratch."""
    stages: set[str] = set()
    images: list[str] = []
    for line in dockerfile.read_text().splitlines():
        found = re.match(r"\s*FROM\s+(?:--platform=\S+\s+)?(\S+)(?:\s+AS\s+(\S+))?", line, re.I)
        copy = re.match(r"\s*COPY\s+(?:--\S+\s+)*--from=(\S+)", line, re.I)
        ref = found.group(1) if found else (copy.group(1) if copy else None)
        if ref and ref.lower() not in stages and ref.lower() != "scratch" and not ref.isdigit() \
                and ref not in images:
            images.append(ref)
        if found and found.group(2):
            stages.add(found.group(2).lower())
    return images


def build_image(manifest: dict) -> dict:
    slug = manifest["slug"]
    folder = FRAMEWORKS / slug
    cmd = ["docker", "build", "--pull", "--progress=plain", "-t", image_tag(slug)]
    build_args = {}
    for name in manifest.get("build_args_from_env", []):
        value = os.environ.get(name, "").strip()
        if value:
            build_args[name] = value
            cmd += ["--build-arg", f"{name}={value}"]
    cmd.append(str(folder))
    log(f"building {slug}")
    started = time.monotonic()
    run(cmd, timeout=3600)
    seconds = round(time.monotonic() - started, 1)
    info = json.loads(run(["docker", "image", "inspect", image_tag(slug)]).stdout)[0]
    return {
        "image_id": info["Id"],
        "image_size_mib": round(info["Size"] / MIB, 1),
        "build_seconds": seconds,
        "build_args": build_args,
        "base_images": {ref: repo_digest(ref) for ref in base_images(folder / "Dockerfile")},
        "versions": read_versions_file(image_tag(slug)),
    }


def repo_digest(ref: str) -> str:
    """The registry digest of an image reference (pinned, local or remote)."""
    if "@sha256:" in ref:
        return ref.split("@", 1)[1]
    local = run(["docker", "image", "inspect", "--format", "{{json .RepoDigests}}", ref], check=False)
    if local.returncode == 0:
        digests = json.loads(local.stdout or "[]")
        if digests:
            return digests[0].split("@", 1)[-1]
    remote = run(["docker", "buildx", "imagetools", "inspect", "--format", "{{json .Manifest}}", ref],
                 check=False, timeout=120)
    if remote.returncode == 0:
        try:
            return json.loads(remote.stdout).get("digest", "unknown")
        except ValueError:
            pass
    return "unknown"


def read_versions_file(image: str) -> str:
    """Read /bench/versions.txt (resolved dependency versions) from an image, if present."""
    created = run(["docker", "create", image], check=False)
    if created.returncode != 0:
        return ""
    cid = created.stdout.strip()
    try:
        # `docker cp ... -` writes a tar stream to stdout.
        result = subprocess.run(["docker", "cp", f"{cid}:/bench/versions.txt", "-"],
                                capture_output=True, check=False, timeout=60)
        if result.returncode != 0:
            return ""
        with tarfile.open(fileobj=io.BytesIO(result.stdout)) as archive:
            member = archive.next()
            handle = archive.extractfile(member) if member else None
            return handle.read().decode("utf-8", "replace").strip() if handle else ""
    finally:
        run(["docker", "rm", "-f", cid], check=False)


def remove(name: str) -> None:
    run(["docker", "rm", "-f", name], check=False)


def start_database(config: dict, cpus: list[int]) -> dict:
    db = config["database"]
    remove(DB_CONTAINER)
    run([
        "docker", "run", "-d", "--name", DB_CONTAINER, "--network", "host",
        "--cpuset-cpus", format_cpu_list(cpus),
        "-e", f"POSTGRES_USER={db['user']}", "-e", f"POSTGRES_PASSWORD={db['password']}",
        "-e", f"POSTGRES_DB={db['name']}",
        "-v", f"{BENCH / 'db'}:/docker-entrypoint-initdb.d:ro",
        db["image"],
        "-c", "listen_addresses=127.0.0.1", "-c", f"port={db['port']}",
        "-c", f"max_connections={db['max_connections']}", "-c", "shared_buffers=256MB",
        *(arg for key, value in db.get("settings", {}).items() for arg in ("-c", f"{key}={value}")),
    ], timeout=600)
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        ready = run(["docker", "exec", DB_CONTAINER, "pg_isready", "-h", "127.0.0.1",
                     "-p", str(db["port"]), "-U", db["user"], "-d", db["name"]], check=False)
        if ready.returncode == 0:
            break
        time.sleep(1)
    else:
        raise BenchError("PostgreSQL did not become ready")
    rows = psql(config, "SELECT count(*) FROM world")
    if rows != str(db["rows"]):
        raise BenchError(f"world table has {rows} rows, expected {db['rows']}")
    fortunes = psql(config, "SELECT count(*) FROM fortune")
    if fortunes != str(db.get("fortune_rows", 12)):
        raise BenchError(f"fortune table has {fortunes} rows, expected {db.get('fortune_rows', 12)}")
    version = psql(config, "SHOW server_version")
    log(f"PostgreSQL {version} ready on CPUs {format_cpu_list(cpus)}")
    return {"image": db["image"], "digest": repo_digest(db["image"]), "version": version,
            "cpus": cpus, "settings": dict(db.get("settings", {}))}


def set_statement_tracking(config: dict, enabled: bool) -> str:
    """Turn pg_stat_statements on (conformance) or off (measurement) for every session.

    The conformance check counts the queries each request runs; measurements
    run without that bookkeeping. Returns the setting new sessions see.
    """
    value = "top" if enabled else "none"
    psql(config, f"ALTER SYSTEM SET pg_stat_statements.track = '{value}'")
    psql(config, "SELECT pg_reload_conf()")
    return psql(config, "SHOW pg_stat_statements.track")


def reset_tables(config: dict) -> None:
    """Give every round the same `world` table: init.sql's values, rewritten without dead rows.

    /updates leaves dead row versions behind; VACUUM FULL rewrites the
    10,000-row table so that later rounds do not measure a bloated table.
    """
    psql(config, "UPDATE world SET randomnumber = 1 + (id * 7919) % 10000")
    psql(config, "VACUUM (FULL, ANALYZE) world")


def database_handle(config: dict) -> "Server":
    """The PostgreSQL container, for its cgroup CPU counter."""
    return Server(DB_CONTAINER, config["database"]["port"])


def psql(config: dict, sql: str) -> str:
    """Run SQL through the container's Unix socket (trusted inside the image)."""
    db = config["database"]
    result = run(["docker", "exec", DB_CONTAINER, "psql", "-p", str(db["port"]),
                  "-U", db["user"], "-d", db["name"], "-v", "ON_ERROR_STOP=1", "-tAc", sql],
                 timeout=60)
    return result.stdout.strip()


def database_url(config: dict) -> str:
    db = config["database"]
    return f"postgres://{db['user']}:{db['password']}@127.0.0.1:{db['port']}/{db['name']}"


def start_server(manifest: dict, config: dict, cpus: list[int], *, keep_logs: bool) -> "Server":
    slug = manifest["slug"]
    name = f"bench-{slug}"
    remove(name)
    server = config["server"]
    env = {
        "PORT": str(server["port"]),
        "DATABASE_URL": database_url(config),
        "DB_POOL_SIZE": str(server["pool_size"]),
        "BENCH_WORKERS": str(len(cpus)),
    }
    env.update({k: str(v) for k, v in manifest.get("env", {}).items()})
    cmd = ["docker", "run", "-d", "--name", name, "--network", "host",
           "--cpuset-cpus", format_cpu_list(cpus),
           "--memory", server["memory"], "--memory-swap", server["memory"],
           "--ulimit", "nofile=65536:65536"]
    # Per-request logs would otherwise be copied by the Docker daemon, outside
    # the server's CPU set; logs are kept only for the conformance start.
    cmd += ["--log-driver", "local"] if keep_logs else ["--log-driver", "none"]
    for key, value in sorted(env.items()):
        cmd += ["-e", f"{key}={value}"]
    cmd.append(image_tag(slug))
    run(cmd, timeout=120)
    return Server(name, server["port"])


class Server:
    """A running server container and its cgroup v2 counters."""

    def __init__(self, name: str, port: int):
        self.name = name
        self.port = port
        self._cgroup: Path | None = None

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def state(self) -> dict:
        result = run(["docker", "inspect", "--format", "{{json .State}}", self.name], check=False)
        if result.returncode != 0:
            return {"Running": False, "Status": "missing"}
        return json.loads(result.stdout)

    def running(self) -> bool:
        return bool(self.state().get("Running"))

    def wait_ready(self, timeout_s: float) -> float:
        started = time.monotonic()
        deadline = started + timeout_s
        while time.monotonic() < deadline:
            if not self.running():
                raise BenchError(f"{self.name} exited during startup: {self.state().get('Status')}")
            try:
                with urllib.request.urlopen(self.base_url + "/text", timeout=2) as response:
                    if response.status == 200:
                        return round(time.monotonic() - started, 2)
            except OSError:
                pass
            time.sleep(READY_POLL_S)
        raise BenchError(f"{self.name} did not answer GET /text within {timeout_s}s")

    def cgroup(self) -> Path:
        if self._cgroup is None:
            pid = self.state().get("Pid")
            if not pid:
                raise BenchError(f"{self.name} has no process")
            line = Path(f"/proc/{pid}/cgroup").read_text().splitlines()[0]
            if not line.startswith("0::"):
                raise BenchError("cgroup v2 is required (unified hierarchy)")
            self._cgroup = Path("/sys/fs/cgroup") / line[3:].lstrip("/")
        return self._cgroup

    def _read(self, name: str) -> str:
        return (self.cgroup() / name).read_text()

    def ram_bytes(self) -> int:
        """memory.current minus inactive file cache (the `docker stats` definition)."""
        current = int(self._read("memory.current"))
        inactive = 0
        for line in self._read("memory.stat").splitlines():
            if line.startswith("inactive_file "):
                inactive = int(line.split()[1])
                break
        return max(current - inactive, 0)

    def memory_peak_bytes(self) -> int | None:
        try:
            return int(self._read("memory.peak"))
        except (OSError, ValueError):
            return None

    def cpu_usec(self) -> int:
        for line in self._read("cpu.stat").splitlines():
            if line.startswith("usage_usec "):
                return int(line.split()[1])
        return 0

    def tasks(self) -> int:
        try:
            return int(self._read("pids.current"))
        except (OSError, ValueError):
            return 0

    def processes(self) -> int:
        try:
            return len(self._read("cgroup.procs").split())
        except OSError:
            return 0

    def logs_tail(self, lines: int = 60) -> str:
        result = run(["docker", "logs", "--tail", str(lines), self.name], check=False)
        return (result.stdout + result.stderr).strip()[-6000:]

    def stop(self) -> None:
        run(["docker", "stop", "-t", "10", self.name], check=False, timeout=60)
        remove(self.name)
