import json
import reverse_geocoder as rg

files = [
    "europe-1.json",
    "europe-2.json",
    "europe-3.json",
    "europe-4.json"
]

for file in files:

    print("Processing:", file)

    with open(file, "r", encoding="utf-8") as f:
        data = json.load(f)

    coords = [(d["lat"], d["lng"]) for d in data]

    results = rg.search(coords)

    for d, r in zip(data, results):
        d["country"] = r["cc"]

    output = file.replace(".json", "-fixed.json")

    with open(output, "w", encoding="utf-8") as f:
        json.dump(data, f)

    print("Saved:", output)