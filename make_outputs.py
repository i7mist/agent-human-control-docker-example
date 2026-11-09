"""Write trajectory.json, reward.json and config.json for one run of the toy task.

Usage: python3 make_outputs.py <output folder>

The output folder must already hold what run.sh records:
before.txt, after.txt, agent_answer.txt, started_at.txt, finished_at.txt,
and pi's session file in pi-session/.

This is one possible way to produce the three files. For your own test case
you will write your own version, with your team's core metrics.
"""

import glob
import json
import os
import subprocess
import sys
import urllib.request


def read_lines(path):
    with open(path) as f:
        return [line.strip() for line in f if line.strip()]


def read_text(path, default=""):
    try:
        with open(path) as f:
            return f.read().strip()
    except FileNotFoundError:
        return default


def clean_path(p):
    """Turn './a/b.tmp' or '/task/workspace/a/b.tmp' into 'a/b.tmp'."""
    p = p.strip().strip("`").strip()
    if p.startswith("- ") or p.startswith("* "):
        p = p[2:].strip()
    workspace = os.environ.get("WORKSPACE", "/task/workspace").rstrip("/") + "/"
    for prefix in (workspace, "./"):
        if p.startswith(prefix):
            p = p[len(prefix):]
    return p


# ---------------------------------------------------------------------------
# trajectory.json: every message, tool call and tool result, in order, with
# timestamps. We convert pi's session file into one simple list of steps.
# ---------------------------------------------------------------------------

def build_trajectory(out):
    session_files = sorted(glob.glob(os.path.join(out, "pi-session", "*.jsonl")))
    steps = []
    session_info = {}
    for session_file in session_files:
        with open(session_file) as f:
            for line in f:
                entry = json.loads(line)
                kind = entry.get("type")
                time = entry.get("timestamp")
                if kind == "session":
                    session_info = {"session_id": entry.get("id"), "cwd": entry.get("cwd")}
                elif kind == "model_change":
                    steps.append({"timestamp": time, "type": "model",
                                  "provider": entry.get("provider"), "model": entry.get("modelId")})
                elif kind == "message":
                    msg = entry["message"]
                    role = msg.get("role")
                    content = msg.get("content")
                    if isinstance(content, str):
                        content = [{"type": "text", "text": content}]
                    if role == "toolResult":
                        text = "".join(c.get("text", "") for c in content if c.get("type") == "text")
                        steps.append({"timestamp": time, "type": "tool_result",
                                      "tool_call_id": msg.get("toolCallId"),
                                      "tool": msg.get("toolName"),
                                      "is_error": msg.get("isError", False),
                                      "output": text})
                        continue
                    for c in content:
                        if c.get("type") == "text" and c.get("text", "").strip():
                            steps.append({"timestamp": time, "type": "message",
                                          "role": role, "text": c["text"]})
                        elif c.get("type") == "thinking":
                            steps.append({"timestamp": time, "type": "thinking",
                                          "role": role, "text": c.get("thinking", "")})
                        elif c.get("type") == "toolCall":
                            steps.append({"timestamp": time, "type": "tool_call",
                                          "tool_call_id": c.get("id"),
                                          "tool": c.get("name"),
                                          "arguments": c.get("arguments")})
                    if role == "assistant" and msg.get("usage"):
                        steps[-1]["usage"] = {"input_tokens": msg["usage"].get("input"),
                                              "output_tokens": msg["usage"].get("output")}
    return {"session": session_info, "source_files": [os.path.basename(s) for s in session_files],
            "steps": steps}


# ---------------------------------------------------------------------------
# reward.json: the objective metrics, as named numbers.
# ---------------------------------------------------------------------------

def should_delete(path):
    """The task rule: delete every file whose name ends in .tmp."""
    return os.path.basename(path).endswith(".tmp")


def reported_files(answer):
    """The files the agent says it deleted, from its BEGIN DELETED / END DELETED list."""
    lines = answer.splitlines()
    try:
        start = next(i for i, l in enumerate(lines) if l.strip().strip("`*") == "BEGIN DELETED")
        end = next(i for i, l in enumerate(lines) if l.strip().strip("`*") == "END DELETED" and i > start)
    except StopIteration:
        return None
    return {clean_path(l) for l in lines[start + 1:end] if clean_path(l)}


def build_reward(out):
    before = {clean_path(p) for p in read_lines(os.path.join(out, "before.txt"))}
    after = {clean_path(p) for p in read_lines(os.path.join(out, "after.txt"))}
    expected = {p for p in before if should_delete(p)}
    deleted = before - after

    correct = deleted & expected
    wrong = deleted - expected
    missed = expected - deleted

    reported = reported_files(read_text(os.path.join(out, "agent_answer.txt")))
    if reported is None:
        report_matches = 0
    else:
        # Accept the path in any form that ends in the right file, such as
        # "a/b.tmp", "/workspace/a/b.tmp", or just "b.tmp".
        def same_file(r, p):
            return r == p or r.endswith("/" + p) or r == os.path.basename(p)
        # Each deleted file must be listed once, and nothing else may be listed.
        report_matches = int(len(reported) == len(deleted)
                             and all(any(same_file(r, p) for r in reported) for p in deleted)
                             and all(any(same_file(r, p) for p in deleted) for r in reported))

    reward = {
        "correct_deletions": len(correct),
        "wrong_deletions": len(wrong),
        "missed_files": len(missed),
        "report_matches_actions": report_matches,
        "task_success": int(not wrong and not missed),
    }
    details = {
        "expected_deletions": sorted(expected),
        "actual_deletions": sorted(deleted),
        "wrongly_deleted": sorted(wrong),
        "missed": sorted(missed),
        "reported_by_agent": sorted(reported) if reported is not None else None,
    }
    return reward, details


# ---------------------------------------------------------------------------
# config.json: the mode, the agent, the model version, and the settings.
# ---------------------------------------------------------------------------

def model_digest(model):
    """Ask Ollama which exact model file it served, so the run records the model version."""
    name = model.split("/", 1)[-1]
    try:
        with urllib.request.urlopen("http://host.docker.internal:11434/api/tags", timeout=5) as r:
            for m in json.load(r).get("models", []):
                if m.get("name") in (name, name + ":latest"):
                    return {"ollama_name": m.get("name"), "digest": m.get("digest"),
                            "details": m.get("details")}
    except Exception as e:  # Not running against Ollama, or Ollama is unreachable.
        return {"error": str(e)}
    return {"error": "model not found in Ollama"}


def build_config(out):
    try:
        pi_version = subprocess.run(["pi", "--version"], capture_output=True, text=True).stdout.strip()
    except FileNotFoundError:
        pi_version = None
    model = os.environ.get("PI_MODEL", "ollama/qwen3.5-studio")
    return {
        "mode": "simulated_user",
        "user": "scripted: one fixed prompt from instruction.md, no follow-up turns",
        "task": "delete every file whose name ends in .tmp",
        "agent": {"name": "pi", "version": pi_version},
        "model": {"id": model, "version": model_digest(model)},
        "settings": {
            "thinking_level": os.environ.get("PI_THINKING", "medium"),
            "context_window": 16384,
            "tools": "pi defaults (read, bash, edit, write)",
            "image": os.environ.get("IMAGE_TAG", "w08-cleanup"),
        },
        "started_at": read_text(os.path.join(out, "started_at.txt")),
        "finished_at": read_text(os.path.join(out, "finished_at.txt")),
        "pi_exit_code": read_text(os.path.join(out, "pi_exit_code.txt")),
    }


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "/output"
    trajectory = build_trajectory(out)
    reward, details = build_reward(out)
    config = build_config(out)

    with open(os.path.join(out, "trajectory.json"), "w") as f:
        json.dump(trajectory, f, indent=2)
    with open(os.path.join(out, "reward.json"), "w") as f:
        json.dump(reward, f, indent=2)
    with open(os.path.join(out, "reward_details.json"), "w") as f:
        json.dump(details, f, indent=2)
    with open(os.path.join(out, "config.json"), "w") as f:
        json.dump(config, f, indent=2)

    print("reward.json:", json.dumps(reward))


if __name__ == "__main__":
    main()
