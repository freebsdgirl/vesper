"""SQLite-backed persistence for cider_agent."""

from __future__ import annotations

import sqlite3
import json
from pathlib import Path
from typing import Any

from .errors import PreferenceStoreError


class PreferenceStore:
    """Store explicit audio preferences in SQLite."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS preferences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL,
                    category TEXT,
                    value TEXT NOT NULL,
                    weight REAL NOT NULL DEFAULT 1.0,
                    note TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_preferences_unique
                ON preferences(kind, COALESCE(category, ''), value)
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_text TEXT NOT NULL,
                    steering_history_json TEXT NOT NULL DEFAULT '[]',
                    mode TEXT NOT NULL DEFAULT 'adaptive',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    last_refilled_at TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS session_tracks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    track_id TEXT,
                    title TEXT,
                    artist TEXT,
                    album TEXT,
                    href TEXT,
                    recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_session_tracks_session_recorded
                ON session_tracks(session_id, recorded_at DESC, id DESC)
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS session_runtime (
                    session_id INTEGER PRIMARY KEY,
                    active_intent TEXT NOT NULL DEFAULT 'active',
                    last_advance_at TEXT,
                    last_selected_track_id TEXT,
                    last_known_playback_state TEXT,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS session_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    track_id TEXT,
                    title TEXT,
                    artist TEXT,
                    album TEXT,
                    href TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_session_events_session_created
                ON session_events(session_id, created_at DESC, id DESC)
                """
            )

    def list_preferences(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, kind, category, value, weight, note, created_at, updated_at
                FROM preferences
                ORDER BY kind ASC, category ASC, value ASC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def remember_preference(
        self,
        *,
        kind: str,
        value: str,
        category: str | None = None,
        weight: float = 1.0,
        note: str | None = None,
    ) -> dict[str, Any]:
        try:
            with self._connect() as connection:
                existing = connection.execute(
                    """
                    SELECT id FROM preferences
                    WHERE kind = ? AND COALESCE(category, '') = COALESCE(?, '') AND value = ?
                    """,
                    (kind, category, value),
                ).fetchone()
                if existing is None:
                    cursor = connection.execute(
                        """
                        INSERT INTO preferences(kind, category, value, weight, note)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (kind, category, value, weight, note),
                    )
                    preference_id = int(cursor.lastrowid)
                else:
                    preference_id = int(existing["id"])
                    connection.execute(
                        """
                        UPDATE preferences
                        SET weight = ?, note = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        (weight, note, preference_id),
                    )
        except sqlite3.Error as exc:
            raise PreferenceStoreError(f"Could not save preference: {exc}") from exc
        return self.get_preference(preference_id)

    def delete_preference(self, preference_id: int) -> bool:
        try:
            with self._connect() as connection:
                cursor = connection.execute("DELETE FROM preferences WHERE id = ?", (preference_id,))
                return cursor.rowcount > 0
        except sqlite3.Error as exc:
            raise PreferenceStoreError(f"Could not delete preference: {exc}") from exc

    def get_preference(self, preference_id: int) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, kind, category, value, weight, note, created_at, updated_at
                FROM preferences
                WHERE id = ?
                """,
                (preference_id,),
            ).fetchone()
        if row is None:
            raise PreferenceStoreError(f"Preference {preference_id} was not found.")
        return dict(row)

    def get_active_session(self) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, request_text, steering_history_json, mode, is_active, created_at, updated_at, last_refilled_at
                FROM sessions
                WHERE is_active = 1
                ORDER BY updated_at DESC, id DESC
                LIMIT 1
                """
            ).fetchone()
        return self._decode_session_row(row) if row is not None else None

    def start_session(self, *, request_text: str, mode: str = "adaptive") -> dict[str, Any]:
        try:
            with self._connect() as connection:
                connection.execute("UPDATE sessions SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE is_active = 1")
                cursor = connection.execute(
                    """
                    INSERT INTO sessions(request_text, steering_history_json, mode, is_active)
                    VALUES (?, '[]', ?, 1)
                    """,
                    (request_text, mode),
                )
                session_id = int(cursor.lastrowid)
        except sqlite3.Error as exc:
            raise PreferenceStoreError(f"Could not start session: {exc}") from exc
        session = self.get_session(session_id)
        if session is None:
            raise PreferenceStoreError(f"Session {session_id} was not found after creation.")
        return session

    def get_session(self, session_id: int) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, request_text, steering_history_json, mode, is_active, created_at, updated_at, last_refilled_at
                FROM sessions
                WHERE id = ?
                """,
                (session_id,),
            ).fetchone()
        return self._decode_session_row(row) if row is not None else None

    def add_session_steering(self, session_id: int, steering_text: str) -> dict[str, Any]:
        session = self.get_session(session_id)
        if session is None:
            raise PreferenceStoreError(f"Session {session_id} was not found.")
        steering_history = list(session.get("steering_history", []))
        steering_history.append(steering_text)
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    UPDATE sessions
                    SET steering_history_json = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (json.dumps(steering_history, ensure_ascii=True), session_id),
                )
        except sqlite3.Error as exc:
            raise PreferenceStoreError(f"Could not update session steering: {exc}") from exc
        updated = self.get_session(session_id)
        if updated is None:
            raise PreferenceStoreError(f"Session {session_id} was not found after update.")
        return updated

    def touch_session_refill(self, session_id: int) -> None:
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    UPDATE sessions
                    SET updated_at = CURRENT_TIMESTAMP, last_refilled_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (session_id,),
                )
        except sqlite3.Error as exc:
            raise PreferenceStoreError(f"Could not update session refill timestamp: {exc}") from exc

    def stop_active_session(self) -> dict[str, Any] | None:
        session = self.get_active_session()
        if session is None:
            return None
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    UPDATE sessions
                    SET is_active = 0, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (session["id"],),
                )
                connection.execute("DELETE FROM session_runtime WHERE session_id = ?", (session["id"],))
        except sqlite3.Error as exc:
            raise PreferenceStoreError(f"Could not stop active session: {exc}") from exc
        session["is_active"] = False
        return session

    def add_session_track(self, session_id: int, track: dict[str, Any]) -> None:
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO session_tracks(session_id, track_id, title, artist, album, href)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        track.get("id"),
                        track.get("title"),
                        track.get("artist"),
                        track.get("album"),
                        track.get("href"),
                    ),
                )
                connection.execute("UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (session_id,))
        except sqlite3.Error as exc:
            raise PreferenceStoreError(f"Could not record session track: {exc}") from exc

    def list_session_tracks(self, session_id: int, *, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT track_id, title, artist, album, href, recorded_at
                FROM session_tracks
                WHERE session_id = ?
                ORDER BY recorded_at DESC, id DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        tracks: list[dict[str, Any]] = []
        for row in rows:
            track_id = str(row["track_id"]).strip() if row["track_id"] is not None else ""
            if not track_id or track_id.lower() == "none":
                continue
            tracks.append(
                {
                    "track_id": track_id,
                    "title": row["title"],
                    "artist": row["artist"],
                    "album": row["album"],
                    "href": row["href"],
                    "recorded_at": row["recorded_at"],
                }
            )
        return tracks

    def list_recent_tracks(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT track_id, title, artist, album, href, recorded_at, session_id
                FROM session_tracks
                ORDER BY recorded_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        tracks: list[dict[str, Any]] = []
        for row in rows:
            track_id = str(row["track_id"]).strip() if row["track_id"] is not None else ""
            if not track_id or track_id.lower() == "none":
                continue
            tracks.append(
                {
                    "session_id": int(row["session_id"]),
                    "track_id": track_id,
                    "title": row["title"],
                    "artist": row["artist"],
                    "album": row["album"],
                    "href": row["href"],
                    "recorded_at": row["recorded_at"],
                }
            )
        return tracks

    def get_session_runtime(self, session_id: int) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT session_id, active_intent, last_advance_at, last_selected_track_id, last_known_playback_state, updated_at
                FROM session_runtime
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "session_id": int(row["session_id"]),
            "active_intent": row["active_intent"],
            "last_advance_at": row["last_advance_at"],
            "last_selected_track_id": row["last_selected_track_id"],
            "last_known_playback_state": row["last_known_playback_state"],
            "updated_at": row["updated_at"],
        }

    def upsert_session_runtime(
        self,
        session_id: int,
        *,
        active_intent: str | None = None,
        last_advance_at: str | None = None,
        last_selected_track_id: str | None = None,
        last_known_playback_state: str | None = None,
    ) -> dict[str, Any]:
        current = self.get_session_runtime(session_id) or {
            "active_intent": "active",
            "last_advance_at": None,
            "last_selected_track_id": None,
            "last_known_playback_state": None,
        }
        resolved_active_intent = current["active_intent"] if active_intent is None else active_intent
        resolved_last_advance_at = current["last_advance_at"] if last_advance_at is None else last_advance_at
        resolved_last_selected_track_id = (
            current["last_selected_track_id"] if last_selected_track_id is None else last_selected_track_id
        )
        resolved_last_known_playback_state = (
            current["last_known_playback_state"] if last_known_playback_state is None else last_known_playback_state
        )
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO session_runtime(
                        session_id,
                        active_intent,
                        last_advance_at,
                        last_selected_track_id,
                        last_known_playback_state,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(session_id) DO UPDATE SET
                        active_intent = excluded.active_intent,
                        last_advance_at = excluded.last_advance_at,
                        last_selected_track_id = excluded.last_selected_track_id,
                        last_known_playback_state = excluded.last_known_playback_state,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (
                        session_id,
                        resolved_active_intent,
                        resolved_last_advance_at,
                        resolved_last_selected_track_id,
                        resolved_last_known_playback_state,
                    ),
                )
        except sqlite3.Error as exc:
            raise PreferenceStoreError(f"Could not update session runtime: {exc}") from exc
        runtime = self.get_session_runtime(session_id)
        if runtime is None:
            raise PreferenceStoreError(f"Session runtime for session {session_id} was not found after update.")
        return runtime

    def clear_session_runtime(self, session_id: int) -> None:
        try:
            with self._connect() as connection:
                connection.execute("DELETE FROM session_runtime WHERE session_id = ?", (session_id,))
        except sqlite3.Error as exc:
            raise PreferenceStoreError(f"Could not clear session runtime: {exc}") from exc

    def add_session_event(
        self,
        session_id: int,
        *,
        event_type: str,
        track: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        track = track or {}
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO session_events(
                        session_id,
                        event_type,
                        track_id,
                        title,
                        artist,
                        album,
                        href,
                        metadata_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        event_type,
                        track.get("track_id") or track.get("id"),
                        track.get("title"),
                        track.get("artist"),
                        track.get("album"),
                        track.get("href"),
                        json.dumps(metadata or {}, ensure_ascii=True),
                    ),
                )
        except sqlite3.Error as exc:
            raise PreferenceStoreError(f"Could not record session event: {exc}") from exc

    def list_session_events(
        self,
        session_id: int,
        *,
        limit: int = 50,
        event_types: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        with self._connect() as connection:
            if event_types:
                placeholders = ", ".join("?" for _ in event_types)
                rows = connection.execute(
                    f"""
                    SELECT id, session_id, event_type, track_id, title, artist, album, href, metadata_json, created_at
                    FROM session_events
                    WHERE session_id = ? AND event_type IN ({placeholders})
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?
                    """,
                    (session_id, *event_types, limit),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT id, session_id, event_type, track_id, title, artist, album, href, metadata_json, created_at
                    FROM session_events
                    WHERE session_id = ?
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?
                    """,
                    (session_id, limit),
                ).fetchall()
        events: list[dict[str, Any]] = []
        for row in rows:
            try:
                metadata = json.loads(row["metadata_json"])
            except (TypeError, json.JSONDecodeError):
                metadata = {}
            events.append(
                {
                    "id": int(row["id"]),
                    "session_id": int(row["session_id"]),
                    "event_type": row["event_type"],
                    "track_id": row["track_id"],
                    "title": row["title"],
                    "artist": row["artist"],
                    "album": row["album"],
                    "href": row["href"],
                    "metadata": metadata if isinstance(metadata, dict) else {},
                    "created_at": row["created_at"],
                }
            )
        return events

    def _decode_session_row(self, row: sqlite3.Row) -> dict[str, Any]:
        try:
            steering_history = json.loads(row["steering_history_json"])
        except (TypeError, json.JSONDecodeError):
            steering_history = []
        return {
            "id": int(row["id"]),
            "request_text": row["request_text"],
            "steering_history": steering_history if isinstance(steering_history, list) else [],
            "mode": row["mode"],
            "is_active": bool(row["is_active"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "last_refilled_at": row["last_refilled_at"],
        }
