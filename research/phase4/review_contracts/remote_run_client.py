"""Remote runner client (Phase 4 room): run one of YOUR scripts on a Modal container (more CPUs / memory, or a GPU).

    sbx python tools/remote_run.py submit runs/<prefix>/my_exp.py --class medium [--timeout 3600] -- --arg1 v1 --arg2 v2
    sbx python tools/remote_run.py wait <job_id> [<job_id> ...]      # polls until done; prints the result summaries
    sbx python tools/remote_run.py status <job_id>
    sbx python tools/remote_run.py classes

See docs/REMOTE_RUNNER.md. Standard library only; it only writes a request file and reads the result file.
"""
import json
import sys
import time
import uuid
from pathlib import Path

import os
PREFIX = os.environ.get("P4_AGENT_SCRATCH", "")           # your prefix = your sandbox scratch name (set by the sandbox)
Q = Path(__file__).resolve().parents[1] / "runs" / PREFIX / "_remote"
CLASSES = {'small': {'cpu': 2.0, 'memory_gb': 8, 'gpu': None}, 'medium': {'cpu': 4.0, 'memory_gb': 16, 'gpu': None}, 'large': {'cpu': 8.0, 'memory_gb': 32, 'gpu': None}, 'xlarge': {'cpu': 8.0, 'memory_gb': 64, 'gpu': None}, 'xxlarge': {'cpu': 16.0, 'memory_gb': 128, 'gpu': None}, 'gpu-t4': {'cpu': 4.0, 'memory_gb': 32, 'gpu': 'T4'}, 'gpu-l4': {'cpu': 4.0, 'memory_gb': 32, 'gpu': 'L4'}, 'gpu-a10g': {'cpu': 4.0, 'memory_gb': 32, 'gpu': 'A10G'}, 'gpu-l40s': {'cpu': 8.0, 'memory_gb': 64, 'gpu': 'L40S'}, 'gpu-a100-40gb': {'cpu': 8.0, 'memory_gb': 64, 'gpu': 'A100-40GB'}, 'gpu-a100-80gb': {'cpu': 8.0, 'memory_gb': 64, 'gpu': 'A100-80GB'}, 'gpu-h100': {'cpu': 8.0, 'memory_gb': 64, 'gpu': 'H100'}, 'gpu-h200': {'cpu': 8.0, 'memory_gb': 128, 'gpu': 'H200'}, 'gpu-b200': {'cpu': 8.0, 'memory_gb': 128, 'gpu': 'B200'}}


def submit(argv):
    script = argv[0].replace("\\", "/")
    if not PREFIX or not script.startswith(f"runs/{PREFIX}/"):
        raise SystemExit(f"run this client through sbx, with a script inside your own runs/<prefix>/ (here: runs/{PREFIX or '?'}/)")
    klass, timeout, rest = "small", 3600, []
    i = 1
    while i < len(argv):
        if argv[i] == "--class":
            klass = argv[i + 1]; i += 2
        elif argv[i] == "--timeout":
            timeout = int(argv[i + 1]); i += 2
        elif argv[i] == "--":
            rest = argv[i + 1:]; break
        else:
            raise SystemExit(f"unknown option {argv[i]} (put the script's own arguments after --)")
    if klass not in CLASSES:
        raise SystemExit(f"--class must be one of {sorted(CLASSES)}")
    job_id = time.strftime("%Y%m%dT%H%M%S") + "_" + uuid.uuid4().hex[:8]
    (Q / "requests").mkdir(parents=True, exist_ok=True)
    tmp = Q / "requests" / f".{job_id}.tmp"
    tmp.write_text(json.dumps({"script": script, "args": rest, "class": klass, "timeout_s": timeout}) + "\n", encoding="utf-8")
    tmp.replace(Q / "requests" / f"{job_id}.json")
    print(job_id)


def status(job_id):
    r = Q / "results" / f"{job_id}.json"
    if r.exists():
        return json.loads(r.read_text(encoding="utf-8"))
    s = Q / "status" / f"{job_id}.json"
    return json.loads(s.read_text(encoding="utf-8")) if s.exists() else {"job_id": job_id, "status": "queued"}


def main():
    cmd, argv = sys.argv[1], sys.argv[2:]
    if cmd == "submit":
        submit(argv)
    elif cmd == "status":
        print(json.dumps(status(argv[0]), indent=1)[:4000])
    elif cmd == "classes":
        for k, v in CLASSES.items():
            print(k, v)
    elif cmd == "wait":
        pending = list(argv)
        while pending:
            for j in list(pending):
                s = status(j)
                if s.get("status") in ("done", "rejected"):
                    print(json.dumps({k: v for k, v in s.items() if k not in ("stdout_tail", "stderr_tail")}, indent=1))
                    print("--- stdout (tail) ---\n" + (s.get("stdout_tail") or "")[-3000:])
                    print("--- stderr (tail) ---\n" + (s.get("stderr_tail") or "")[-3000:])
                    pending.remove(j)
            if pending:
                time.sleep(10)
    else:
        raise SystemExit("commands: submit, status, wait, classes")


if __name__ == "__main__":
    main()
