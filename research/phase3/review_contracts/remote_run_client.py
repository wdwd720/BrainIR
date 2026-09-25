"""Remote runner client (clean room): run one of YOUR scripts on a Modal container with more memory / CPUs.

    uv run python runs/_remote/remote_run.py submit runs/<prefix>/my_exp.py --class medium [--timeout 3600] -- --arg1 v1 --arg2 v2
    uv run python runs/_remote/remote_run.py wait <job_id> [<job_id> ...]      # polls until done; prints the result summaries
    uv run python runs/_remote/remote_run.py status <job_id>

See notes/_remote_runner.md. Standard library only; it only writes a request file and reads the result file.
"""
import json
import sys
import time
import uuid
from pathlib import Path

Q = Path(__file__).resolve().parent / "queue"


def submit(argv):
    script = argv[0]
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
        raise SystemExit("commands: submit, status, wait")


if __name__ == "__main__":
    main()
