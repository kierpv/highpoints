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
UMAP_COUNTRY_LAYERS = {
    "CZ": [0],
}

CZ_COMMUNICATION_POLES = {
    "BUKOVA HORA",
    "JAVORICE",
    "JILOVISTE",
    "KLET",
    "KOJAL",
    "KOSETICE",
    "KRASNE",
    "KRASOV",
    "LIBLICE",
    "OSTRAVA",
    "PARDUBICE",
    "PRADED",
    "PRAHA",
}


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


def meters_from_feet(value):
    height = parse_height(value)
    if height is None:
        return None
    meters = float(height) * 0.3048
    return round(meters, 1)


def first_value(props, names):
    for name in names:
        value = props.get(name)
        if value not in (None, ""):
            return value
    return None


def parse_feature_height(props):
    # Official obstacle datasets use AGL feet/meters fields; prefer those over
    # OSM-style "height", which is sometimes polluted with elevation-like data.
    official_meters = first_value(props, ["maxHeightAGL"])
    if official_meters is not None:
        return parse_height(official_meters), "official"

    official_feet = first_value(props, ["HGT AGL (FT)", "height_FT", "valHgt (ft)"])
    if official_feet is not None:
        return meters_from_feet(official_feet), "official"

    height = parse_height(props.get("height"))
    if height is None:
        return None, "unknown"
    return height, "osm"


def parse_umap_height(props):
    height = parse_height(props.get("height_m"))
    if height is not None:
        return height
    return parse_height(props.get("height"))


def clean_type(value):
    text = clean_text(value).upper()
    return text.replace(" ", "_").replace("-", "_")


def infer_type(props):
    raw = first_value(props, ["type", "obstacleType", "txtDescrType", "TYPE", "Geometry type"])
    text = clean_type(raw)
    name = clean_type(first_value(props, ["name", "txtName"]))
    combined = f"{text} {name}"

    if any(token in combined for token in ("CHIMNEY", "STACK", "SMOKESTACK", "SCHORNSTEIN")):
        return "CHIMNEY"
    if any(token in combined for token in ("WIND_TURBINE", "WINDTURBINE", "WIND_TURB", "WINDMILL", "WINDKRAFT", "WINDENERGIE", "TURBINE")):
        return "WIND_TURBINE"
    if "COOLING" in combined:
        return "COOLING_TOWER"
    if "CRANE" in combined:
        return "CRANE"
    if "ANTENNA" in combined:
        return "ANTENNA"
    if "MAST" in combined and any(token in combined for token in ("COMM", "RADIO", "BROADCAST", "TELECOM", "FUNK", "SENDER")):
        return "MAST_COMMUNICATION"
    if "TOWER" in combined and any(token in combined for token in ("COMM", "RADIO", "BROADCAST", "TELECOM", "FUNK", "SENDER")):
        return "TOWER_COMMUNICATION"
    if "MAST" in combined:
        return "MAST"
    if "TOWER" in combined:
        return "TOWER"
    if "POLE" in combined or "PYLON" in combined or "LINE" in combined:
        return "POLE"
    return text or "OTHER"


def keep_feature_height(record, source):
    if record["h"] is None:
        return True
    if source == "official":
        if record["country"] == "FR" and record["t"] in {
            "CABLE_CAR",
            "CABLE_ABOVE_VALLEY_BOTTOM",
            "CATENARY",
        }:
            record["h"] = None
        if record["country"] == "CH" and record["t"] in {
            "POLE",
            "CATENARY",
            "CABLE_CAR",
            "CABLE_ABOVE_VALLEY_BOTTOM",
            "TRANSMISSION_LINE",
        }:
            record["h"] = None
        return True

    # OSM-style telecom heights above this range are often polluted by AMSL,
    # total object/elevation imports, or plain bad tags. Official obstacle
    # fields, parsed above, are still kept.
    if record["t"] in {"MAST_COMMUNICATION", "TOWER_COMMUNICATION", "MAST", "TOWER"}:
        name = clean_type(record["n"])
        is_named_transmitter = (
            name.startswith("SENDER")
            or name.startswith("SENDEMAST")
            or "TRANSMITTER" in name
            or "EMETTEUR" in name
            or "ÉMETTEUR" in name
            or "PYLONE" in name
            or "PYLÔNE" in name
        )
        if record["h"] > 250 and not is_named_transmitter:
            record["h"] = None
    return True


def normalize_record(record):
    row = {
        "n": clean_text(record.get("n") or record.get("name")) or "—",
        "t": clean_text(record.get("t") or record.get("type")).upper() or "OTHER",
        "h": parse_height(record.get("h") if "h" in record else record.get("height")),
        "lat": record.get("lat"),
        "lng": record.get("lng"),
        "city": clean_text(record.get("city")) or "—",
        "country": clean_text(record.get("country")),
    }
    if row["t"] in {"MAST_COMMUNICATION", "TOWER_COMMUNICATION"} and row["h"] is not None and row["h"] > 350:
        name = clean_type(row["n"])
        if name in {"", "—"}:
            row["h"] = None
    return row


def record_score(record):
    score = 0
    if record.get("h") is not None:
        score += 30 if record.get("_height_source") == "official" else 10
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
    height, height_source = parse_feature_height(props)
    record = {
        "n": clean_text(first_value(props, ["name", "txtName", "Designation"])) or "—",
        "t": infer_type(props),
        "h": height,
        "lat": round(lat, 7),
        "lng": round(lng, 7),
        "city": "—",
        "country": country,
        "_height_source": height_source,
        "_operator": clean_text(props.get("operator")),
        "_osm_id": clean_text(props.get("osm_id")),
    }
    if country == "FR" and height_source == "official" and record["t"] == "POLE":
        record["t"] = "MAST"
    keep_feature_height(record, height_source)
    return record


def umap_feature_to_record(feature, country):
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
        "t": infer_type(props),
        "h": parse_umap_height(props),
        "lat": round(lat, 7),
        "lng": round(lng, 7),
        "city": "—",
        "country": country,
        "_height_source": "umap",
    }
    if country == "CZ" and record["t"] == "POLE" and clean_text(record["n"]).upper() in CZ_COMMUNICATION_POLES:
        record["t"] = "MAST_COMMUNICATION"
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


def load_umap_layers():
    path = ROOT / "map.umap"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    layers = data.get("layers", [])
    rows = []
    for country, indexes in UMAP_COUNTRY_LAYERS.items():
        for index in indexes:
            if index >= len(layers):
                continue
            for feature in layers[index].get("features", []):
                row = umap_feature_to_record(feature, country)
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
        row.pop("_height_source", None)
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
    replaced = set(MERGED_FILES) | set(UMAP_COUNTRY_LAYERS)
    kept_existing = [row for row in existing if row["country"] not in replaced]
    merged = load_merged_geojson()
    umap_rows = load_umap_layers()
    final_rows = dedupe(kept_existing + merged + umap_rows)
    write_split(final_rows)

    merged_stats = stats(final_rows)
    print(f"existing rows: {len(existing):,}")
    print(f"merged source rows: {len(merged):,}")
    print(f"uMap source rows: {len(umap_rows):,}")
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
