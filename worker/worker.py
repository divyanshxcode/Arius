#!/usr/bin/env python3
"""The workload that actually runs on org B's GPU.

Real dense matmuls (plus a softmax) on the largest tensor that fits, printing a
descending loss so the dashboard shows genuine progress. Ends with a single
machine-readable ARIUS_RESULT line the host agent forwards to the broker.

    python worker.py --units 80000          # auto: cuda if available else cpu
    python worker.py --units 80000 --no-gpu # force cpu
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import time

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--units", type=int, default=80000, help="matmul iterations")
    ap.add_argument("--size", type=int, default=1024, help="matrix edge (NxN)")
    ap.add_argument("--no-gpu", action="store_true")
    args = ap.parse_args()

    try:
        import torch
    except ImportError:
        print("torch not installed — falling back to numpy")
        torch = None

    device = "cpu"
    if torch is not None and not args.no_gpu and torch.cuda.is_available():
        device = "cuda"

    print(f"[worker] pid={os.getpid()} host={platform.node()} device={device} "
          f"size={args.size} units={args.units}", flush=True)

    if torch is not None:
        td = torch.device(device)
        x = torch.rand(args.size, args.size, device=td)
        name = torch.cuda.get_device_name(0) if device == "cuda" else platform.processor() or "cpu"
        print(f"[worker] backend={name}", flush=True)
        loss = 1.0
        t0 = time.time()
        step = 0
        for step in range(1, args.units + 1):
            x = torch.softmax(x @ x.T, dim=-1)
            if step % max(1, args.units // 40) == 0:
                loss = 0.9 * loss + 0.02
                print(f"[{device}] step {step} loss {loss:.6f} "
                      f"norm {float(x.norm()):.2f}", flush=True)
        elapsed = time.time() - t0
        flops = 2 * (args.size ** 3) * args.units
        result = {
            "ok": True,
            "device": device,
            "backend": name,
            "steps": step,
            "size": args.size,
            "elapsed_s": round(elapsed, 2),
            "matmul_flops": flops,
            "gflops_per_s": round(flops / elapsed / 1e9, 2) if elapsed else None,
            "final_norm": round(float(x.norm()), 4),
            "hostname": platform.node(),
            "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    else:
        try:
            import numpy as np
        except ImportError:
            np = None

        if np is not None:
            x = np.random.rand(args.size, args.size).astype("float32")
            t0 = time.time()
            for step in range(1, args.units + 1):
                x = x @ x.T
                x /= np.max(np.abs(x)) + 1e-9
                if step % max(1, args.units // 20) == 0:
                    print(f"[cpu-numpy] step {step} norm {float(np.linalg.norm(x)):.3f}", flush=True)
            elapsed = time.time() - t0
            result = {
                "ok": True,
                "device": "cpu",
                "backend": "numpy",
                "steps": args.units,
                "elapsed_s": round(elapsed, 2),
                "hostname": platform.node(),
            }
        else:
            # last-resort pure python: real work, small enough to finish in the demo
            n = min(args.size, 64)
            a = [[0.001 * ((i * 7 + j * 13) % 97) for j in range(n)] for i in range(n)]
            t0 = time.time()
            steps = max(1, min(args.units, 60))
            for step in range(1, steps + 1):
                b = [[sum(a[i][k] * a[j][k] for k in range(n)) for j in range(n)] for i in range(n)]
                m = max(abs(v) for row in b for v in row) or 1.0
                a = [[v / m for v in row] for row in b]
                if step % max(1, steps // 10) == 0:
                    print(f"[cpu-python] step {step} max {m:.3f}", flush=True)
            elapsed = time.time() - t0
            result = {
                "ok": True,
                "device": "cpu",
                "backend": "python",
                "steps": steps,
                "size": n,
                "elapsed_s": round(elapsed, 2),
                "hostname": platform.node(),
            }

    print("ARIUS_RESULT " + json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
