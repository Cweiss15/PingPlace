"""
services/subway_service.py — NYC Subway Transit Routing

Calculates estimated subway travel time between two coordinates using a
graph-based routing model with Dijkstra's algorithm.

Route cost:  walk_to_station + train_time (+ transfer penalties) + walk_to_dest
"""

import math
import heapq
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WALKING_SPEED_KMH = 4.8          # standard pedestrian speed
MAX_WALK_KM = 1.5                 # maximum acceptable walk to/from a station
TRANSFER_PENALTY_MIN = 5          # minutes added when changing subway lines
NEAREST_STATION_CANDIDATES = 3   # entry-point candidates to try


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class SubwayStation:
    id: str
    name: str
    lat: float
    lng: float
    lines: list


@dataclass(order=True)
class _PQEntry:
    """Priority-queue entry for Dijkstra."""
    cost: float
    station_id: str = field(compare=False)
    prev_line: str = field(compare=False)


# ---------------------------------------------------------------------------
# Starter dataset — core Manhattan + Brooklyn stations
#
# Structure is intentionally simple so a load_gtfs() function can replace
# or extend STATIONS and EDGES with full MTA data without touching the
# algorithm at all (see "Extending with GTFS" in the README).
# ---------------------------------------------------------------------------

STATIONS: dict[str, SubwayStation] = {s.id: s for s in [
    # --- 1/2/3 ---
    SubwayStation("96st_1",        "96 St",                     40.8394, -73.9661, ["1", "2", "3"]),
    SubwayStation("72st_1",        "72 St",                     40.8288, -73.9800, ["1", "2", "3"]),
    SubwayStation("times_sq_1",    "Times Sq–42 St",            40.7549, -73.9874, ["1", "2", "3", "N", "Q", "R", "W", "7", "S"]),
    SubwayStation("chambers_123",  "Chambers St",               40.7143, -74.0087, ["1", "2", "3"]),
    SubwayStation("fulton_123",    "Fulton St",                 40.7092, -74.0079, ["1", "2", "3"]),

    # --- 4/5/6 ---
    SubwayStation("86st_456",      "86 St",                     40.7771, -73.9561, ["4", "5", "6"]),
    SubwayStation("59st_456",      "59 St–Lexington Av",        40.7626, -73.9676, ["4", "5", "6"]),
    SubwayStation("grand_central", "Grand Central–42 St",       40.7527, -73.9772, ["4", "5", "6", "7", "S"]),
    SubwayStation("14st_456",      "14 St–Union Sq",            40.7352, -73.9902, ["4", "5", "6", "L", "N", "Q", "R", "W"]),
    SubwayStation("fulton_456",    "Fulton St",                 40.7092, -74.0079, ["4", "5", "6", "A", "C", "J", "Z", "2", "3"]),
    SubwayStation("wall_st",       "Wall St",                   40.7069, -74.0089, ["4", "5"]),

    # --- N/Q/R/W ---
    SubwayStation("57st_nqrw",     "57 St–7 Av",                40.7649, -73.9803, ["N", "Q", "R", "W"]),
    SubwayStation("49st_nqrw",     "49 St",                     40.7599, -73.9839, ["N", "Q", "R", "W"]),
    SubwayStation("34st_nqrw",     "34 St–Herald Sq",           40.7490, -73.9878, ["N", "Q", "R", "W", "B", "D", "F", "M"]),
    SubwayStation("23st_nqrw",     "23 St",                     40.7429, -73.9886, ["N", "Q", "R", "W"]),
    SubwayStation("canal_nqrw",    "Canal St",                  40.7191, -74.0007, ["N", "Q", "R", "W"]),
    SubwayStation("dekalb",        "DeKalb Av",                 40.6914, -73.9817, ["B", "D", "N", "Q", "R", "W"]),
    SubwayStation("atlantic",      "Atlantic Av–Barclays Ctr",  40.6840, -73.9770, ["B", "D", "N", "Q", "R", "2", "3", "4", "5"]),

    # --- A/C/E ---
    SubwayStation("columbus_ace",  "59 St–Columbus Circle",     40.7681, -73.9819, ["A", "C", "B", "D", "1"]),
    SubwayStation("42st_ace",      "42 St–Port Authority",      40.7572, -74.0018, ["A", "C", "E"]),
    SubwayStation("34st_ace",      "34 St–Penn Station",        40.7487, -73.9995, ["A", "C", "E", "1", "2", "3"]),
    SubwayStation("14st_ace",      "14 St",                     40.7401, -74.0042, ["A", "C", "E"]),
    SubwayStation("west4th",       "W 4 St–Wash Sq",            40.7323, -74.0003, ["A", "C", "E", "B", "D", "F", "M"]),
    SubwayStation("chambers_ace",  "Chambers St",               40.7143, -74.0087, ["A", "C"]),
    SubwayStation("fulton_ace",    "Fulton St",                 40.7092, -74.0079, ["A", "C"]),
    SubwayStation("jay_st",        "Jay St–MetroTech",          40.6924, -73.9872, ["A", "C", "F"]),
    SubwayStation("hoyt_sch",      "Hoyt–Schermerhorn",         40.6884, -73.9850, ["A", "C", "G"]),

    # --- B/D/F/M ---
    SubwayStation("47_50_bdfm",    "47–50 Sts–Rockefeller Ctr", 40.7587, -73.9815, ["B", "D", "F", "M"]),
    SubwayStation("42st_bdfm",     "42 St–Bryant Park",         40.7546, -73.9838, ["B", "D", "F", "M"]),
    SubwayStation("herald_sq",     "Herald Sq",                 40.7490, -73.9878, ["B", "D", "F", "M", "N", "Q", "R", "W"]),
    SubwayStation("broadway_laf",  "Broadway–Lafayette St",     40.7253, -73.9963, ["B", "D", "F", "M"]),
    SubwayStation("2av_f",         "2 Av",                      40.7226, -73.9893, ["F"]),
    SubwayStation("bergen_f",      "Bergen St",                 40.6809, -73.9903, ["F", "G"]),
    SubwayStation("7av_f",         "7 Av",                      40.6666, -73.9781, ["F", "G"]),

    # --- L ---
    SubwayStation("8av_l",         "8 Av",                      40.7396, -74.0022, ["L"]),
    SubwayStation("6av_l",         "6 Av",                      40.7379, -73.9988, ["L"]),
    SubwayStation("14st_l_3av",    "3 Av",                      40.7322, -73.9889, ["L"]),
    SubwayStation("1av_l",         "1 Av",                      40.7307, -73.9815, ["L"]),
    SubwayStation("bedford_l",     "Bedford Av",                40.7171, -73.9563, ["L"]),
    SubwayStation("lorimer_l",     "Lorimer St",                40.7143, -73.9502, ["L", "G"]),

    # --- G ---
    SubwayStation("nassau_g",      "Nassau Av",                 40.7243, -73.9512, ["G"]),
    SubwayStation("clinton_g",     "Clinton–Washington Avs",    40.6882, -73.9689, ["G"]),

    # --- J/Z ---
    SubwayStation("essex_jmz",     "Essex St",                  40.7184, -73.9876, ["J", "M", "Z"]),
    SubwayStation("myrtle_jmz",    "Myrtle Av",                 40.6973, -73.9354, ["J", "M", "Z"]),

    # --- 7 ---
    SubwayStation("5av_7",         "5 Av",                      40.7542, -73.9799, ["7"]),
    SubwayStation("queensboro_7",  "Queensboro Plaza",          40.7508, -73.9401, ["7", "N", "W"]),
    SubwayStation("jackson_hts",   "Jackson Hts–Roosevelt Av",  40.7466, -73.8912, ["7", "E", "F", "M", "R"]),

    # --- 2/3 Brooklyn ---
    SubwayStation("nevins_23",     "Nevins St",                 40.6884, -73.9801, ["2", "3"]),
    SubwayStation("bergen_23",     "Bergen St",                 40.6808, -73.9752, ["2", "3"]),
    SubwayStation("grand_army",    "Grand Army Plaza",          40.6752, -73.9709, ["2", "3"]),
]}


# Directed edges: station_id → list of (to_station_id, line, travel_minutes)
_RAW_EDGES: list[tuple[str, str, str, float]] = [
    # 1/2/3 trunk
    ("96st_1",       "72st_1",        "1",  3.5),
    ("72st_1",       "times_sq_1",    "1",  9.0),
    ("times_sq_1",   "chambers_123",  "1",  7.0),
    ("chambers_123", "fulton_123",    "1",  2.5),
    # 2/3 express skip
    ("96st_1",       "times_sq_1",    "2",  6.0),
    ("times_sq_1",   "fulton_123",    "2",  7.0),
    ("fulton_123",   "nevins_23",     "2",  4.0),
    ("nevins_23",    "bergen_23",     "2",  2.0),
    ("bergen_23",    "grand_army",    "3",  3.5),
    ("atlantic",     "bergen_23",     "2",  2.5),
    ("atlantic",     "nevins_23",     "3",  2.0),

    # 4/5/6
    ("86st_456",     "59st_456",      "4",  5.0),
    ("59st_456",     "grand_central", "4",  4.5),
    ("grand_central","14st_456",      "4",  6.5),
    ("14st_456",     "fulton_456",    "4",  5.0),
    ("fulton_456",   "wall_st",       "4",  2.0),
    ("86st_456",     "59st_456",      "6",  5.0),
    ("59st_456",     "grand_central", "6",  4.5),
    ("grand_central","14st_456",      "6",  7.0),

    # N/Q/R/W
    ("57st_nqrw",    "49st_nqrw",     "N",  2.0),
    ("49st_nqrw",    "times_sq_1",    "N",  2.5),
    ("times_sq_1",   "34st_nqrw",     "N",  4.0),
    ("34st_nqrw",    "23st_nqrw",     "N",  2.5),
    ("23st_nqrw",    "14st_456",      "N",  3.0),
    ("14st_456",     "canal_nqrw",    "N",  5.5),
    ("canal_nqrw",   "dekalb",        "Q",  8.0),
    ("dekalb",       "atlantic",      "Q",  2.5),
    ("57st_nqrw",    "49st_nqrw",     "R",  2.0),
    ("49st_nqrw",    "times_sq_1",    "R",  2.5),

    # A/C/E
    ("columbus_ace", "42st_ace",      "A",  5.0),
    ("42st_ace",     "34st_ace",      "A",  3.0),
    ("34st_ace",     "14st_ace",      "A",  4.0),
    ("14st_ace",     "west4th",       "A",  3.0),
    ("west4th",      "chambers_ace",  "A",  4.5),
    ("chambers_ace", "fulton_ace",    "A",  2.0),
    ("fulton_ace",   "jay_st",        "A",  4.0),
    ("jay_st",       "hoyt_sch",      "A",  2.0),
    ("columbus_ace", "42st_ace",      "C",  5.5),
    ("42st_ace",     "34st_ace",      "E",  3.0),

    # B/D/F/M
    ("columbus_ace", "47_50_bdfm",    "B",  4.0),
    ("47_50_bdfm",   "42st_bdfm",     "B",  2.0),
    ("42st_bdfm",    "34st_nqrw",     "B",  4.0),
    ("34st_nqrw",    "west4th",       "B",  5.0),
    ("west4th",      "broadway_laf",  "B",  4.0),
    ("broadway_laf", "dekalb",        "B",  7.0),
    ("dekalb",       "atlantic",      "B",  2.5),
    ("47_50_bdfm",   "42st_bdfm",     "F",  2.0),
    ("42st_bdfm",    "herald_sq",     "F",  2.5),
    ("herald_sq",    "west4th",       "F",  5.0),
    ("west4th",      "2av_f",         "F",  3.0),
    ("2av_f",        "jay_st",        "F",  5.5),
    ("jay_st",       "bergen_f",      "F",  5.0),
    ("bergen_f",     "7av_f",         "F",  4.0),

    # L
    ("8av_l",        "6av_l",         "L",  2.5),
    ("6av_l",        "14st_456",      "L",  2.0),
    ("14st_456",     "14st_l_3av",    "L",  2.5),
    ("14st_l_3av",   "1av_l",         "L",  2.0),
    ("1av_l",        "bedford_l",     "L",  5.0),
    ("bedford_l",    "lorimer_l",     "L",  2.5),

    # G
    ("nassau_g",     "lorimer_l",     "G",  2.5),
    ("lorimer_l",    "clinton_g",     "G",  5.5),
    ("clinton_g",    "hoyt_sch",      "G",  3.0),
    ("hoyt_sch",     "bergen_f",      "G",  3.5),
    ("bergen_f",     "7av_f",         "G",  4.0),

    # J/M/Z
    ("essex_jmz",    "myrtle_jmz",    "J",  8.0),

    # 7
    ("times_sq_1",   "5av_7",         "7",  3.0),
    ("5av_7",        "grand_central", "7",  2.0),
    ("grand_central","queensboro_7",  "7",  8.0),
    ("queensboro_7", "jackson_hts",   "7",  9.0),
]

# Build bidirectional adjacency list
EDGES: dict[str, list[tuple[str, str, float]]] = {sid: [] for sid in STATIONS}
for src, dst, line, mins in _RAW_EDGES:
    EDGES[src].append((dst, line, mins))
    EDGES[dst].append((src, line, mins))   # subway runs both directions


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Straight-line distance between two GPS coordinates in kilometres."""
    r = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (math.sin(d_lat / 2) ** 2
         + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2))
         * math.sin(d_lng / 2) ** 2)
    return r * 2 * math.asin(math.sqrt(a))


def _walk_minutes(km: float) -> float:
    """Convert kilometres to walking minutes at WALKING_SPEED_KMH."""
    return (km / WALKING_SPEED_KMH) * 60.0


def _nearest_stations(lat: float, lng: float, k: int = NEAREST_STATION_CANDIDATES):
    """
    Return the k nearest stations within MAX_WALK_KM, sorted by walking time.
    Each item: (station_id, walk_minutes)
    """
    candidates = []
    for sid, station in STATIONS.items():
        km = _haversine_km(lat, lng, station.lat, station.lng)
        if km <= MAX_WALK_KM:
            candidates.append((sid, _walk_minutes(km)))
    candidates.sort(key=lambda x: x[1])
    return candidates[:k]


# ---------------------------------------------------------------------------
# Dijkstra's algorithm
# ---------------------------------------------------------------------------

def _dijkstra(entry_stations: list[tuple[str, float]]) -> dict[str, tuple[float, list, str]]:
    """
    Run Dijkstra from multiple entry stations simultaneously.

    Args:
        entry_stations: list of (station_id, initial_cost_minutes)

    Returns:
        dict mapping station_id → (best_cost, path_as_route_segments, last_line)
    """
    # cost, path, last_line used for transfer penalty detection
    best: dict[str, tuple[float, list, str]] = {}
    pq: list[_PQEntry] = []

    for sid, walk_cost in entry_stations:
        entry = _PQEntry(cost=walk_cost, station_id=sid, prev_line="")
        heapq.heappush(pq, entry)
        best[sid] = (walk_cost, [], "")

    while pq:
        entry = heapq.heappop(pq)
        cur_cost, cur_id, cur_line = entry.cost, entry.station_id, entry.prev_line

        stored_cost, stored_path, stored_line = best.get(cur_id, (math.inf, [], ""))
        if cur_cost > stored_cost:
            continue  # stale queue entry

        for (neighbour, line, travel_min) in EDGES.get(cur_id, []):
            # Apply transfer penalty when the line changes mid-journey
            transfer = TRANSFER_PENALTY_MIN if (cur_line and line != cur_line) else 0
            new_cost = cur_cost + travel_min + transfer

            n_cost, n_path, n_line = best.get(neighbour, (math.inf, [], ""))
            if new_cost < n_cost:
                new_path = stored_path + [(cur_id, line, travel_min, transfer > 0)]
                best[neighbour] = (new_cost, new_path, line)
                heapq.heappush(pq, _PQEntry(cost=new_cost, station_id=neighbour, prev_line=line))

    return best


# ---------------------------------------------------------------------------
# Route narrative builder
# ---------------------------------------------------------------------------

def _build_route_narrative(
    origin_walk_min: float,
    entry_station: SubwayStation,
    path_edges: list[tuple],
    exit_station: SubwayStation,
    dest_walk_min: float,
) -> tuple[list[str], int, float, float]:
    """
    Convert the raw Dijkstra path into human-readable route steps.

    Returns:
        (route_steps, transfer_count, train_minutes, walking_minutes)
    """
    steps: list[str] = []
    transfers = 0
    train_minutes = 0.0

    steps.append(f"Walk {round(origin_walk_min)} min to {entry_station.name}")

    if not path_edges:
        # Origin and destination share the same station
        steps.append(f"Walk {round(dest_walk_min)} min to destination")
        return steps, 0, 0.0, origin_walk_min + dest_walk_min

    # Group consecutive edges by line into "segments"
    segments: list[tuple[str, str, float]] = []  # (from_name, line, cumulative_min)
    current_line = path_edges[0][1]
    segment_min = 0.0
    segment_start = entry_station.name

    for (station_id, line, travel_min, is_transfer) in path_edges:
        if is_transfer:
            # Close previous segment
            segments.append((segment_start, current_line, segment_min + travel_min))
            segment_start = STATIONS[station_id].name
            current_line = line
            segment_min = 0.0
            transfers += 1
        else:
            segment_min += travel_min

    # Close last segment
    segments.append((segment_start, current_line, segment_min))

    for (from_name, line, seg_min) in segments:
        train_minutes += seg_min
        # Destination of this segment is the exit station
        steps.append(f"Take {line} train from {from_name}")

    if transfers:
        steps.append(f"Transfer {transfers}× (approx {transfers * TRANSFER_PENALTY_MIN} min wait)")

    steps.append(f"Walk {round(dest_walk_min)} min to destination")

    walking_minutes = origin_walk_min + dest_walk_min
    return steps, transfers, train_minutes, walking_minutes


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def calculate_subway_eta(
    origin_lat: float, origin_lng: float,
    dest_lat: float,   dest_lng: float,
) -> dict:
    """
    Calculate estimated subway travel time between two coordinates.

    Returns a dict with keys:
        minutes         – total journey time (int)
        walkingMinutes  – combined walking time (int)
        trainMinutes    – time spent on trains (int)
        transfers       – number of line changes (int)
        route           – list of human-readable route steps
        status          – "OK" | "NO_ROUTE" | "ERROR"
        error           – present only when status != "OK"
    """
    entry_candidates = _nearest_stations(origin_lat, origin_lng)
    if not entry_candidates:
        return {
            "minutes": None,
            "walkingMinutes": None,
            "trainMinutes": None,
            "transfers": None,
            "route": [],
            "status": "NO_ROUTE",
            "error": "No subway station within walking distance of origin",
        }

    exit_candidates = _nearest_stations(dest_lat, dest_lng)
    if not exit_candidates:
        return {
            "minutes": None,
            "walkingMinutes": None,
            "trainMinutes": None,
            "transfers": None,
            "route": [],
            "status": "NO_ROUTE",
            "error": "No subway station within walking distance of destination",
        }

    # Seed Dijkstra with all entry candidates and their walking costs
    dijkstra_result = _dijkstra(entry_candidates)

    best_total = math.inf
    best_route: Optional[dict] = None

    for exit_sid, exit_walk_min in exit_candidates:
        if exit_sid not in dijkstra_result:
            continue
        train_cost, path_edges, last_line = dijkstra_result[exit_sid]

        # Walk cost to the entry station (built into train_cost via Dijkstra seed)
        # Recover origin walk from path or seed
        origin_walk = next(w for s, w in entry_candidates if s == path_edges[0][0]) if path_edges else 0.0
        total = train_cost + exit_walk_min

        if total < best_total:
            best_total = total
            entry_sid = path_edges[0][0] if path_edges else exit_sid
            best_route = {
                "entry_station": STATIONS[entry_sid],
                "exit_station": STATIONS[exit_sid],
                "path_edges": path_edges,
                "origin_walk_min": origin_walk,
                "exit_walk_min": exit_walk_min,
                "train_cost": train_cost - origin_walk,
            }

    if best_route is None:
        return {
            "minutes": None,
            "walkingMinutes": None,
            "trainMinutes": None,
            "transfers": None,
            "route": [],
            "status": "NO_ROUTE",
            "error": "No subway route found between these locations",
        }

    route_steps, transfers, train_min, walk_min = _build_route_narrative(
        origin_walk_min=best_route["origin_walk_min"],
        entry_station=best_route["entry_station"],
        path_edges=best_route["path_edges"],
        exit_station=best_route["exit_station"],
        dest_walk_min=best_route["exit_walk_min"],
    )

    total_min = round(best_total)

    return {
        "minutes":        total_min,
        "walkingMinutes": round(walk_min),
        "trainMinutes":   round(train_min),
        "transfers":      transfers,
        "route":          route_steps,
        "status":         "OK",
    }
