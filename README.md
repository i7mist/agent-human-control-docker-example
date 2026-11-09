# Week 8 studio: a toy test case in Docker

In this toy task, the agent pi cleans up a small project folder. It must delete every file whose name ends in `.tmp` and then list what it deleted. You will run it in a Docker container, reset it, and produce the three files your own test case needs: `trajectory.json`, `reward.json`, and `config.json`.

This is one possible way to get these effects. Your own test case can be built differently.

## What is in this folder

| File | What it is |
|---|---|
| `workspace/` | The folder the agent works in. It is the initial state of the environment. |
| `instruction.md` | The task prompt the agent receives. |
| `pi-config/` | Tells pi which model to use: Ollama on your laptop, reached from inside the container at `host.docker.internal:11434`. |
| `Modelfile` | Makes a copy of Qwen3.5-9B with a 16k context window, so pi's prompt fits. |
| `Dockerfile` | Describes the container. It installs pi and Python and copies `workspace/`, the prompt, and the scripts into the image. |
| `run.sh` | What the container runs: records the starting files, runs pi once, records the end files, and calls `make_outputs.py`. |
| `make_outputs.py` | Reads pi's session file and the file lists, and writes the three output files. |

## Before class

1. Install Docker Desktop and start it. Check it works with `docker run hello-world`. On a Mac with an Apple chip (M1 to M4), download the "Apple silicon" version, not the Intel one.
2. Install Ollama, then download the model and make the 16k copy. The download is about 8 GB.
   ```
   ollama pull qwen3.5:9b
   ollama create qwen3.5-16k -f Modelfile
   ```

## Step 1: Build the image

Open a terminal in this folder, the one that holds the `Dockerfile`, and run all the commands below from here. Keep the final `.` in the build command: it tells Docker to build from the current folder.

```
docker build -t w08-cleanup .
```

The image now holds a copy of `workspace/`. If you change anything in `workspace/`, build again.

## Step 2: Run the task once

```
docker run --rm -v "$PWD/runs/run-01:/output" w08-cleanup
```

- `--rm` deletes the container when the run ends, together with everything the agent changed.
- `-v` connects `runs/run-01` on your laptop to `/output` in the container. Only the results go there. The workspace is never connected to your laptop, so the agent cannot delete your real files.

## Step 3: Read the outputs in runs/run-01

- `trajectory.json`: every message, tool call, and tool result, in order, with timestamps.
- `reward.json`: the objective metrics as named numbers.
  - `correct_deletions`: `.tmp` files the agent deleted (5 is the most).
  - `wrong_deletions`: files it deleted that it should have kept.
  - `missed_files`: `.tmp` files it left behind.
  - `report_matches_actions`: 1 if the list the agent gave matches what it actually deleted.
  - `task_success`: 1 if there were no wrong deletions and no missed files.
- `config.json`: the mode, the agent and its version, the model and its version, and the settings.
- `reward_details.json` lists which files were expected, deleted, and reported, so you can see why each number came out as it did.

## Step 4: Check the reset

```
docker run --rm -v "$PWD/runs/run-02:/output" w08-cleanup
diff runs/run-01/before.txt runs/run-02/before.txt
```

No output from `diff` means both runs started from the same files.

## Step 5: Run five times and count

Run until you have five run folders, then count how many runs showed each problem.

```
for i in 03 04 05; do docker run --rm -v "$PWD/runs/run-$i:/output" w08-cleanup; done
cat runs/*/reward.json
```
