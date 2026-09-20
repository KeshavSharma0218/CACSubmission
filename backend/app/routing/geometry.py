"""Dependency-free geographic helpers shared by graph construction and routing."""

import math

from app.database.schemas import Coordinate


def haversine_m(a: Coordinate, b: Coordinate) -> float:
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dp = math.radians(b.lat - a.lat)
    dl = math.radians(b.lon - a.lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6_371_000 * 2 * math.atan2(math.sqrt(h), math.sqrt(1 - h))


def nearest_node(point: Coordinate, nodes: dict[str, Coordinate]) -> str:
    return min(nodes, key=lambda node: haversine_m(point, nodes[node]))


def encode_polyline(points: list[Coordinate], precision: int = 5) -> str:
    output = []
    prev_lat = prev_lon = 0
    scale = 10**precision
    for p in points:
        lat, lon = round(p.lat * scale), round(p.lon * scale)
        for value in (lat - prev_lat, lon - prev_lon):
            value = ~(value << 1) if value < 0 else value << 1
            while value >= 0x20:
                output.append(chr((0x20 | (value & 0x1F)) + 63))
                value >>= 5
            output.append(chr(value + 63))
        prev_lat, prev_lon = lat, lon
    return "".join(output)


def decode_polyline(value: str, precision: int = 5) -> list[Coordinate]:
    coords = []
    index = lat = lon = 0
    scale = 10**precision
    while index < len(value):
        changes = []
        for _ in range(2):
            result = shift = 0
            while True:
                byte = ord(value[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if byte < 0x20:
                    break
            changes.append(~(result >> 1) if result & 1 else result >> 1)
        lat += changes[0]
        lon += changes[1]
        coords.append(Coordinate(lat=lat / scale, lon=lon / scale))
    return coords
