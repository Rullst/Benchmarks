"""Host inspection: CPU topology and split, CPU time counters, environment record."""

from __future__ import annotations

import os
import platform
from pathlib import Path

from common import BenchError, run


def parse_cpu_list(text: str) -> list[int]:
    """Parse a kernel CPU list such as '0-1,4,6-7'."""
    cpus: list[int] = []
    for part in text.strip().split(","):
        if not part:
            continue
        if "-" in part:
            low, high = part.split("-", 1)
            cpus.extend(range(int(low), int(high) + 1))
        else:
            cpus.append(int(part))
    return sorted(set(cpus))


def format_cpu_list(cpus: list[int]) -> str:
    return ",".join(str(c) for c in sorted(cpus))


def sibling_groups(cpus: list[int], sys_root: Path = Path("/sys/devices/system/cpu")) -> list[list[int]]:
    """Group the usable CPUs by physical core (SMT siblings together)."""
    usable = set(cpus)
    groups: list[list[int]] = []
    seen: set[int] = set()
    for cpu in sorted(usable):
        if cpu in seen:
            continue
        path = sys_root / f"cpu{cpu}" / "topology" / "thread_siblings_list"
        try:
            siblings = set(parse_cpu_list(path.read_text())) & usable
        except OSError:
            siblings = {cpu}
        siblings.add(cpu)
        groups.append(sorted(siblings))
        seen |= siblings
    return groups


def split_cpus(cpus: list[int], server_count: int, groups: list[list[int]]) -> tuple[list[int], list[int]]:
    """Give the server whole physical cores first; everything else is the client side.

    With SMT the server gets both threads of one core, so it does not share a
    core with the load generator or the database.
    """
    if len(cpus) < server_count + 2:
        raise BenchError(f"need at least {server_count + 2} CPUs, found {len(cpus)}")
    server: list[int] = []
    for group in groups:
        if len(server) >= server_count:
            break
        server.extend(group[: server_count - len(server)])
    client = [c for c in cpus if c not in server]
    return sorted(server), sorted(client)


def split_database(client: list[int], database_count: int) -> tuple[list[int], list[int]]:
    """Give PostgreSQL its own CPUs (the last ones of the client side), or share them (0).

    Returns (load generator CPUs, database CPUs); with 0 both are the whole
    client side, as in the default configuration.
    """
    if database_count <= 0:
        return client, client
    if len(client) <= database_count:
        raise BenchError(f"need more than {database_count} client CPUs to give the database its own, "
                         f"found {len(client)}")
    return client[:-database_count], client[-database_count:]


def cpu_split(server_count: int, min_cpus: int, database_count: int = 0) -> dict:
    """The server, load generator ("client") and database CPU sets.

    "client" is where the load generator and the harness run; "database" is
    where PostgreSQL runs, the same CPUs as "client" unless database_count
    gives it its own.
    """
    cpus = sorted(os.sched_getaffinity(0))
    if len(cpus) < min_cpus:
        raise BenchError(
            f"this runner has {len(cpus)} usable CPUs; the suite needs at least {min_cpus}"
        )
    groups = sibling_groups(cpus)
    server, client = split_cpus(cpus, server_count, groups)
    loadgen, database = split_database(client, database_count)
    return {"all": cpus, "server": server, "client": loadgen, "database": database,
            "database_shared": database == loadgen, "core_groups": groups}


def read_cpu_times(cpus: list[int], stat_text: str | None = None) -> tuple[int, int]:
    """Return (busy, total) jiffies summed over the given CPUs from /proc/stat."""
    if stat_text is None:
        stat_text = Path("/proc/stat").read_text()
    wanted = {f"cpu{c}" for c in cpus}
    busy = total = 0
    for line in stat_text.splitlines():
        fields = line.split()
        if not fields or fields[0] not in wanted:
            continue
        # user nice system idle iowait irq softirq steal (guest time is in user)
        values = [int(v) for v in fields[1:9]]
        idle = values[3] + values[4]
        total += sum(values)
        busy += sum(values) - idle
    return busy, total


def busy_fraction(before: tuple[int, int], after: tuple[int, int]) -> float:
    busy = after[0] - before[0]
    total = after[1] - before[1]
    return busy / total if total > 0 else 0.0


def _output(cmd: list[str]) -> str:
    try:
        return run(cmd, check=False, timeout=60).stdout.strip()
    except BenchError as exc:
        return f"unavailable: {exc}"


def mem_total_mib() -> float:
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemTotal:"):
            return round(int(line.split()[1]) / 1024, 1)
    return 0.0


def environment(split: dict, loadgen: dict) -> dict:
    """Everything needed to judge whether two runs are comparable."""
    env = os.environ
    os_release = {}
    try:
        for line in Path("/etc/os-release").read_text().splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                os_release[key] = value.strip('"')
    except OSError:
        pass
    return {
        "runner": {
            "name": env.get("RUNNER_NAME", ""),
            "image_os": env.get("ImageOS", ""),
            "image_version": env.get("ImageVersion", ""),
            "github_run_id": env.get("GITHUB_RUN_ID", ""),
            "github_sha": env.get("GITHUB_SHA", ""),
        },
        "os": os_release.get("PRETTY_NAME", platform.platform()),
        "kernel": platform.release(),
        "cpu_count": len(split["all"]),
        "cpu_model": _cpu_model(),
        "cpu_split": split,
        "memory_total_mib": mem_total_mib(),
        "lscpu": _output(["lscpu"]),
        "lscpu_topology": _output(["lscpu", "--extended=CPU,CORE,SOCKET,NODE,MAXMHZ"]),
        "docker": _output(["docker", "version", "--format",
                           "client {{.Client.Version}}, server {{.Server.Version}}"]),
        "python": platform.python_version(),
        "load_generator": loadgen,
    }


def _cpu_model() -> str:
    for line in Path("/proc/cpuinfo").read_text().splitlines():
        if line.startswith("model name"):
            return line.split(":", 1)[1].strip()
    return platform.processor()
