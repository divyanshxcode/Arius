#!/usr/bin/env bash
# Verify this machine can actually run the Phase 4 "real compute" beat.
set -u
echo "=== GPU check ==="
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
  echo
  echo "=== Docker GPU passthrough check ==="
  if command -v docker >/dev/null 2>&1; then
    docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi \
      || echo "GPU passthrough FAILED — install NVIDIA Container Toolkit"
  else
    echo "docker missing — worker will run with device=cpu"
  fi
else
  echo "no nvidia-smi: worker.py will fall back to device=cpu (supported mode)"
fi
