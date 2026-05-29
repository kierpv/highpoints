import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOWNLOADS = Path.home() / "Downloads"

MERGED_FILES = {
    "FI": ["Finland_merged_part1.geojson"],
    "FR": ["France_merged_part1.geojson", "France_merged_part2.geojson"],
    "DE": ["Germany_merged_part1.geojson", "Germany_merged_part2.geojson", "Germany_merged_part3.geojson"],
    "NO": ["Norway_merged_part1.geojson"],
    "CH": ["Switzerland_merged_part1.geojson", "Switzerland_merged_part2.geojson"],
    "GB": ["United_Kingdom_merged_part1.geojson"],
}

EUROPE_FILES = ["europe-1.json", "europe-2.json", "europe-3.json"]


def clean_text(value):
    if value is None:
        return ""
    text = str(value).strip()
    return text if text else ""


def parse_height(value):
    if value is None or value == "":
        return None
    try:
        height = float(str(value).replace(",", "."))
    except ValueError:
        return None
    if not height or height < 0:
        return None
    return round(height, 2) if height % 1 else int(height)


def normalize_record(record):
    return {
        "n": clean_text(record.get("n") or record.get("name")) or "—",
        "t": clean_text(record.get("t") or record.get("type")).upper() or "OTHER",
        "h": parse_height(record.get("h") if "h" in record else record.get("height")),
        "lat": record.get("lat"),
        "lng": record.get("lng"),
        "city": clean_text(record.get("city")) or "—",
        "country": clean_text(record.get("country")),
    }


def record_score(record):
    score = 0
    if record.get("h") is not None:
        score += 10
    if record.get("n") and record["n"] != "—":
        score += 5
    if record.get("city") and record["city"] != "—":
        score += 2
    if record.get("t") and record["t"] != "OTHER":
        score += 2
    score += len(str(record.get("_operator") or "")) > 0
    score += len(str(record.get("_osm_id") or "")) > 0
    return score


def merge_richer(existing, candidate):
    if record_score(candidate) > record_score(existing):
        existing, candidate = candidate, existing
    for key in ("n", "t", "h", "city"):
        if (existing.get(key) in (None, "", "—", "OTHER")) and candidate.get(key) not in (None, "", "—", "OTHER"):
            existing[key] = candidate[key]
    return existing


def coord_key(record):
    return (
        record["country"],
        round(float(record["lat"]), 5),
        round(float(record["lng"]), 5),
    )


def feature_to_record(feature, country):
    geometry = feature.get("geometry") or {}
    coords = geometry.get("coordinates") or []
    if geometry.get("type") != "Point" or len(coords) < 2:
        return None
    props = feature.get("properties") or {}
    try:
        lng = float(coords[0])
        lat = float(coords[1])
    except (TypeError, ValueError):
        return None
    record = {
        "n": clean_text(props.get("name")) or "—",
        "t": clean_text(props.get("type")).upper() or "OTHER",
        "h": parse_height(props.get("height")),
        "lat": round(lat, 7),
        "lng": round(lng, 7),
        "city": "—",
        "country": country,
        "_operator": clean_text(props.get("operator")),
        "_osm_id": clean_text(props.get("osm_id")),
    }
    return record


def load_existing_europe():
    rows = []
    for name in EUROPE_FILES:
        rows.extend(json.loads((ROOT / name).read_text(encoding="utf-8")))
    return [normalize_record(row) for row in rows]


def load_merged_geojson():
    rows = []
    for country, names in MERGED_FILES.items():
        for name in names:
            path = DOWNLOADS / name
            data = json.loads(path.read_text(encoding="utf-8"))
            for feature in data.get("features", []):
                row = feature_to_record(feature, country)
                if row:
                    rows.append(row)
    return rows


def dedupe(rows):
    deduped = {}
    for row in rows:
        if row.get("lat") is None or row.get("lng") is None or not row.get("country"):
            continue
        key = coord_key(row)
        deduped[key] = merge_richer(deduped[key], row) if key in deduped else row
    clean_rows = []
    for row in deduped.values():
        row.pop("_operator", None)
        row.pop("_osm_id", None)
        clean_rows.append(row)
    return clean_rows


def write_split(rows):
    rows = sorted(rows, key=lambda r: (r["country"], r["lat"], r["lng"], r["t"], r["n"]))
    chunk_size = (len(rows) + len(EUROPE_FILES) - 1) // len(EUROPE_FILES)
    for index, name in enumerate(EUROPE_FILES):
        chunk = rows[index * chunk_size : (index + 1) * chunk_size]
        (ROOT / name).write_text(json.dumps(chunk, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def stats(rows):
    by_country = {}
    for row in rows:
        country = row["country"]
        item = by_country.setdefault(country, {"total": 0, "with_height": 0, "over_100m": 0, "max": 0})
        item["total"] += 1
        if row["h"] is not None:
            item["with_height"] += 1
            if row["h"] > 100:
                item["over_100m"] += 1
            item["max"] = max(item["max"], row["h"])
    return by_country


def main():
    existing = load_existing_europe()
    replaced = set(MERGED_FILES)
    kept_existing = [row for row in existing if row["country"] not in replaced]
    merged = load_merged_geojson()
    final_rows = dedupe(kept_existing + merged)
    write_split(final_rows)

    merged_stats = stats(final_rows)
    print(f"existing rows: {len(existing):,}")
    print(f"merged source rows: {len(merged):,}")
    print(f"final rows: {len(final_rows):,}")
    for country in sorted(replaced):
        item = merged_stats.get(country, {})
        print(
            f"{country}: {item.get('total', 0):,} total, "
            f"{item.get('with_height', 0):,} with height, "
            f"{item.get('over_100m', 0):,} over 100m, "
            f"max {item.get('max', 0)}m"
        )


if __name__ == "__main__":
    main()
