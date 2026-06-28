"""Track matching and scoring helpers extracted from :class:`CiderAgentService`.

These are pure or near-pure functions over search results that do not depend on
service state. ``top_pool_order`` needs a random instance and a default pool
size, which the service passes through when it delegates.
"""

from __future__ import annotations

import random
import re
from typing import Any


def normalize_match_text(value: str | None) -> str:
    if value is None:
        return ""
    normalized = value.casefold()
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return " ".join(normalized.split())


def normalize_title_match_text(value: str | None) -> str:
    if value is None:
        return ""
    simplified = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", value)
    simplified = re.sub(
        r"\s+-\s+(version|ver|movie ver|movie version|instrumental|cover|edit|mix|remaster(?:ed)?)\b.*$",
        "",
        simplified,
        flags=re.IGNORECASE,
    )
    return normalize_match_text(simplified)


def best_track_match(tracks: list[dict[str, Any]], *, title: str, artist: str) -> dict[str, Any] | None:
    title_norm = normalize_match_text(title)
    title_base_norm = normalize_title_match_text(title)
    artist_norm = normalize_match_text(artist)
    for track in tracks:
        if normalize_match_text(track.get("title")) == title_norm and normalize_match_text(track.get("artist")) == artist_norm:
            return track
    for track in tracks:
        track_title = normalize_match_text(track.get("title"))
        track_artist = normalize_match_text(track.get("artist"))
        if title_norm in track_title and artist_norm == track_artist:
            return track
    if title_base_norm:
        for track in tracks:
            track_title_base = normalize_title_match_text(track.get("title"))
            track_artist = normalize_match_text(track.get("artist"))
            if track_artist != artist_norm:
                continue
            if track_title_base == title_base_norm:
                return track
        for track in tracks:
            track_title_base = normalize_title_match_text(track.get("title"))
            track_artist = normalize_match_text(track.get("artist"))
            if track_artist != artist_norm:
                continue
            if title_base_norm in track_title_base or track_title_base in title_base_norm:
                return track
    return None


def best_playlist_match(playlists: list[dict[str, Any]], *, playlist_name: str) -> dict[str, Any] | None:
    target = normalize_match_text(playlist_name)
    if not target:
        return None
    for playlist in playlists:
        if normalize_match_text(playlist.get("name")) == target:
            return playlist
    for playlist in playlists:
        name = normalize_match_text(playlist.get("name"))
        if target in name or name in target:
            return playlist
    return None


def artist_track_score(track: dict[str, Any]) -> tuple[int, int]:
    album = normalize_match_text(track.get("album"))
    album_score = 0
    if "greatest hits" in album:
        album_score += 5
    if "essential" in album:
        album_score += 4
    return (album_score, 0)


def top_pool_order(
    tracks: list[dict[str, Any]],
    *,
    take: int,
    rng: random.Random,
    pool_size: int | None = None,
    default_pool_size: int,
) -> list[dict[str, Any]]:
    if take <= 0 or not tracks:
        return []
    bounded_pool = max(1, min(pool_size or default_pool_size, len(tracks)))
    top_pool = list(tracks[:bounded_pool])
    rng.shuffle(top_pool)
    ordered = top_pool + list(tracks[bounded_pool:])
    return ordered[:take]


def best_artist_track_matches(
    tracks: list[dict[str, Any]],
    *,
    artist: str,
    limit: int,
    rng: random.Random,
    pool_size: int,
) -> list[dict[str, Any]]:
    artist_norm = normalize_match_text(artist)
    exact_artist_tracks = [track for track in tracks if normalize_match_text(track.get("artist")) == artist_norm]
    if not exact_artist_tracks:
        return []
    scored = sorted(exact_artist_tracks, key=artist_track_score, reverse=True)
    return top_pool_order(scored, take=limit, rng=rng, default_pool_size=pool_size)


def best_artist_track_match(
    tracks: list[dict[str, Any]],
    *,
    artist: str,
    rng: random.Random,
    pool_size: int,
) -> dict[str, Any] | None:
    matches = best_artist_track_matches(tracks, artist=artist, limit=1, rng=rng, pool_size=pool_size)
    return matches[0] if matches else None
