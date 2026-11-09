#!/bin/bash
# Runs the toy task once inside the container and writes the results to /output.
set -u
OUT=/output
mkdir -p "$OUT"
cd /task/workspace

# Record the starting state, so you can check that the environment was reset.
find . -type f | sort > "$OUT/before.txt"
date -u +%Y-%m-%dT%H:%M:%SZ > "$OUT/started_at.txt"

# Run the agent once, non-interactively, with the task prompt.
pi --print --offline \
   --model "${PI_MODEL:-ollama/qwen3.5-studio}" \
   --thinking "${PI_THINKING:-medium}" \
   --session-dir "$OUT/pi-session" \
   "$(cat /task/instruction.md)" \
   > "$OUT/agent_answer.txt" 2> "$OUT/pi_errors.txt"
echo $? > "$OUT/pi_exit_code.txt"

date -u +%Y-%m-%dT%H:%M:%SZ > "$OUT/finished_at.txt"

# Record the end state, then compute the three output files.
find . -type f | sort > "$OUT/after.txt"
python3 /task/make_outputs.py "$OUT"
