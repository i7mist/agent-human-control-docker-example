import csv
from statistics import mean

with open("data/responses.csv") as f:
    rows = list(csv.DictReader(f))

workload = [int(r["workload"]) for r in rows]
clarity = [int(r["clarity"]) for r in rows]

with open("output/summary.txt", "w") as out:
    out.write(f"Responses: {len(rows)}\n")
    out.write(f"Mean workload rating: {mean(workload):.2f}\n")
    out.write(f"Mean clarity rating: {mean(clarity):.2f}\n")
