"""
Google Trends -> Pytrends -> GIS-ready cache
- Single entry point that wires together payload -> views -> persisted outputs.
- Safe retries/backoff for undocumented throttling (HTTP 429).
"""

from __future__ import annotations
from pathlib import Path
import datetime
import time
import json
import pandas as pd
from pytrends.request import TrendReq

# ----------------------------
# Configuration (edit here)
# ----------------------------
CONFIG = {
    "batches": [
        {
            "terms": ["ArcGIS Pro", "geospatial AI", "geoai", "QGIS", "geospatial ai tools"],
            "timeframe": "today 5-y",   # use 'now 7-d' for hourly/local windows
            "geo": "US",                  # '' = worldwide; 'US' or 'US-IL' etc.
            "gprop": ""                 # '', 'news', 'images', 'youtube', 'froogle'
        }
    ],
    "tz_minutes": 360,                   # US Central example
    "output_dir": "trends_cache",
    "retry_attempts": 5,
    "retry_pause_seconds": 45,           # base pause; increases each attempt
    "include_low_volume_regions": True,
    "include_geo_codes": True
}

# ----------------------------
# Utilities
# ----------------------------
def now_tag() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

def mkdirp(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)

def save_parquet(df: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=True)
    return path

def save_json(obj, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, default=str)
    return path

def with_backoff(callable_, attempts: int, pause: int, *args, **kwargs):
    """
    General retry/backoff wrapper for pytrends calls.
    """
    last_exc = None
    for k in range(attempts):
        try:
            return callable_(*args, **kwargs)
        except Exception as ex:
            last_exc = ex
            # Linear/exponential backoff: pause * (k+1)
            time.sleep(pause * (k + 1))
    raise RuntimeError(f"Call failed after {attempts} attempts") from last_exc

# ----------------------------
# Pytrends client (shared)
# ----------------------------
def make_client(tz_minutes: int) -> TrendReq:
    """
    Unofficial client; no Google account or key required.
    Note: rate limits are undocumented—keep calls civil.
    """
    return TrendReq(
        hl="en-US",
        tz=tz_minutes,
        retries=3,
        backoff_factor=3,
        timeout=(10, 25)
    )

# ----------------------------
# Core job
# ----------------------------
def run_job(client: TrendReq, batch: dict, outdir: Path, attempts: int, pause: int) -> dict:
    """
    1) build_payload (scope)
    2) interest_over_time
    3) interest_by_region
    4) related_queries
    5) trending (optional, independent of payload)
    """
    terms = batch["terms"]
    timeframe = batch["timeframe"]
    geo = batch["geo"]
    gprop = batch["gprop"]

    # Tag files for traceability
    tag = f"{now_tag()}__{geo or 'WW'}__{gprop or 'web'}__{timeframe.replace(' ', '_')}"
    stem = f"{'-'.join([t.replace(' ', '_') for t in terms])[:80]}__{tag}"  # truncate for long filenames

    # 1) Payload defines scope for dependent calls
    client.build_payload(
        kw_list=terms,
        cat=0,
        timeframe=timeframe,
        geo=geo,
        gprop=gprop
    )

    manifest = {
        "terms": terms,
        "timeframe": timeframe,
        "geo": geo,
        "gprop": gprop,
        "tag": tag,
        "artifacts": {}
    }

    # 2) Interest over time
    iot = with_backoff(client.interest_over_time, attempts, pause)
    iot_path = outdir / f"iot__{stem}.parquet"
    save_parquet(iot, iot_path)
    manifest["artifacts"]["interest_over_time"] = str(iot_path)

    # 3) Interest by region (choropleth-ready)
    ibr = with_backoff(
        client.interest_by_region,
        attempts,
        pause,
        resolution="COUNTRY",
        inc_low_vol=CONFIG["include_low_volume_regions"],
        inc_geo_code=CONFIG["include_geo_codes"]
    )
    ibr = ibr.reset_index().rename(columns={"geoName": "region"})
    ibr_path = outdir / f"ibr_country__{stem}.parquet"
    save_parquet(ibr, ibr_path)
    manifest["artifacts"]["interest_by_region_country"] = str(ibr_path)

    # 4) Related queries (discovery)
    rq = with_backoff(client.related_queries, attempts, pause)
    rq_path = outdir / f"related_queries__{stem}.json"
    # Convert DataFrames to dict for JSON
    rq_serializable = {}
    for term, parts in rq.items():
        rq_serializable[term] = {}
        for k, df in parts.items():
            rq_serializable[term][k] = df.to_dict(orient="records") if isinstance(df, pd.DataFrame) else None
    save_json(rq_serializable, rq_path)
    manifest["artifacts"]["related_queries"] = str(rq_path)

    # 5) Trending and realtime (these do not depend on the current payload)
    daily_us = with_backoff(client.trending_searches, attempts, pause, pn="united_states")
    daily_path = outdir / f"trending_daily_US__{tag}.parquet"
    save_parquet(daily_us, daily_path)
    manifest["artifacts"]["trending_daily_us"] = str(daily_path)

    rt_us = with_backoff(client.realtime_trending_searches, attempts, pause, pn="US")
    rt_path = outdir / f"trending_realtime_US__{tag}.parquet"
    save_parquet(rt_us, rt_path)
    manifest["artifacts"]["trending_realtime_us"] = str(rt_path)

    # Save manifest (audit trail for downstream apps)
    manifest_path = outdir / f"manifest__{stem}.json"
    save_json(manifest, manifest_path)
    manifest["manifest_path"] = str(manifest_path)
    return manifest

# ----------------------------
# Main
# ----------------------------
def main():
    outdir = Path(CONFIG["output_dir"])
    mkdirp(outdir)
    client = make_client(CONFIG["tz_minutes"])

    all_manifests = []
    for batch in CONFIG["batches"]:
        # Important: limit <=5 terms per payload for stability
        assert 1 <= len(batch["terms"]) <= 5, "Use <=5 terms per payload"
        m = run_job(
            client=client,
            batch=batch,
            outdir=outdir,
            attempts=CONFIG["retry_attempts"],
            pause=CONFIG["retry_pause_seconds"]
        )
        all_manifests.append(m)

    # Index of the run
    index_path = outdir / f"index__{now_tag()}.json"
    save_json(all_manifests, index_path)
    print(f"Wrote {index_path}")
    for m in all_manifests:
        print(json.dumps(m, indent=2))

if __name__ == "__main__":
    main()
