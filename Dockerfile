# The environment for the toy task: pi, Python, and the project folder.
FROM node:22-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# The agent. Pin the version so every run uses the same harness.
RUN npm install -g @earendil-works/pi-coding-agent@0.86.1

# Tell pi which model to use (see pi-config/models.json).
COPY pi-config/ /root/.pi/agent/

# The task prompt and the scripts that run the task and write the outputs.
COPY instruction.md run.sh make_outputs.py /task/
RUN chmod +x /task/run.sh

# The initial state of the environment. Every container starts from this copy.
COPY workspace/ /task/workspace/

WORKDIR /task/workspace
CMD ["/task/run.sh"]
