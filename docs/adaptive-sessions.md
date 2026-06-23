# Adaptive Sessions, Search, and Preferences

This page answers the practical behavior questions that come up when using or changing Vesper's text-first music flow.

## Session vs. One-Track Playback

Vesper has two different playback modes:

| Mode | What starts it | What happens after the first track? |
| --- | --- | --- |
| One-track/direct playback | Direct commands such as `play`, `pause`, `stop`, `play_search_result`, or a specific candidate match | Vesper performs that action once. Cider may continue its own native queue/autoplay behavior, but Vesper is not actively choosing future tracks. |
| Adaptive session | Text requests resolved to `play_session`, such as `play some music`, `play upbeat morning music`, or artist/vibe/activity requests | Vesper creates an active session, clears Cider's queue, chooses a first real track, records session state, and lets the background worker choose later tracks. |

An adaptive session is therefore not just “play one result.” It is persistent state plus a selection loop.

Starting a new session replaces any existing active session. `stop` stops playback and ends the active session; `stop_session` ends only the session state.

## What Preferences Do

Preferences are explicit music memory stored in SQLite by `PreferenceStore`.

Current preference types:

- `liked_track` — a track the user explicitly liked.
- `favored_artist` — the artist of a liked track, recorded so future vague sessions can seed from that artist.
- `globally_rejected_track` — a track the user explicitly rejected; future session candidate pools filter these out.

### Does “I like this” save a preference?

Yes, when the text resolver is configured and resolves the request to `like_current_track`.

The resolver prompt explicitly says to use `like_current_track` when the user says they like the current song or track. So messages like these are intended to save a preference for the currently playing track:

- `i like this`
- `i like this track`
- `this song is good`

When `like_current_track` runs, Vesper:

1. reads the current Cider playback snapshot;
2. requires a current track ID;
3. upserts a `liked_track` preference;
4. upserts a `favored_artist` preference when the current track has an artist;
5. if a session is active, records a `track_liked` session event;
6. leaves playback running.

If the fallback resolver is the only resolver, broad phrases like `i like this` are not understood; the fallback resolver only handles simple direct commands. In that case, call the structured/internal action through code or enable the OpenAI-compatible resolver.

### How preferences affect future sessions

Preferences are used in two main ways:

1. **Vague-session seeding.** Requests like `play some music` can bootstrap from saved preference cues before asking the resolver to invent a new search direction. Vesper uses liked tracks' previous session queries, favored artists, and liked tracks as seeds.
2. **Avoidance.** Globally rejected tracks are excluded from future session candidate pools.

Preferences do not currently act like a global recommender profile for every possible search. They are most important for vague session starts and repeat/rejection avoidance.

View preferences with:

```bash
vesper preferences list
```

Delete one with:

```bash
vesper preferences forget <preference_id>
```

## Search Source Types

Adaptive sessions use typed search sources. A source is `{kind, term}`.

Supported resolver-planned kinds:

| Kind | When the resolver should use it | What Vesper does with it |
| --- | --- | --- |
| `artist` | Artist names, including artist-plus-mood requests. The term should be only the artist name. | Searches Apple Music catalog artists, chooses the exact normalized match or first result, then fetches that artist's top songs. |
| `genre` | Only when the term exactly matches an Apple Music supported genre name loaded from `/genres`. | Fetches Apple Music chart songs for that genre ID. |
| `vibe` | Descriptive requests, activities, moods, unsupported subgenres, genre-plus-mood phrases, and broad contextual requests. | Searches Apple Music catalog playlists for the term, asks the resolver to choose the best playlist, then fetches tracks from that playlist. |

Internal/transitional kinds:

| Kind | Purpose |
| --- | --- |
| `preference` | Synthetic source used for preference-seeded vague sessions. It is backed by an in-memory pool built from liked tracks, favored artists, and preference cues. |
| `legacy` | Compatibility source for older resolver output that only returned query strings. It behaves like catalog track search. |

## How the LLM Chooses Search Types

For adaptive-session planning, the OpenAI-compatible resolver receives:

- the original session request;
- recent session steering;
- compact playback state;
- a small preference sample;
- supported Apple Music genre names;
- rejected search sources;
- the current timestamp.

Its planning instruction is constrained:

- use `artist` for artist names;
- use `genre` only for exact supported genre names;
- use `vibe` for moods, activities, unsupported subgenres, descriptive requests, and genre-plus-mood requests;
- preserve concrete user descriptors instead of unnecessarily narrowing them;
- use creative interpretation mainly for open-ended/contextual/activity requests;
- do not invent final tracks.

The resolver returns only the source. Vesper performs the real Apple Music lookup.

## Is the User's Search Used Verbatim?

It depends on the path.

### Direct search actions

Direct search methods such as `search_catalog_tracks(query)` and `play_search_result(query=...)` use the provided query string for Apple Music search after light cleanup/validation. These are the closest thing to verbatim search.

The text resolver may normalize phrases before calling those actions. For example, resolver normalization strips leading phrases like `play`, `find`, `search for`, `songs by`, or `popular songs by` from direct search queries.

### Adaptive sessions

Adaptive sessions are not guaranteed verbatim. The resolver plans a typed source from the user's request. For concrete requests it is instructed to preserve the broad request; for open-ended requests it may take creative license.

Examples:

- `play trip-hop` should stay broad, not become a narrower invented vibe like `atmospheric trip hop` unless the user asked for that.
- `music for cleaning the house` may become a more search-friendly vibe/source.
- `play Beyoncé` should become an `artist` source with term `Beyoncé`.

There is not currently a user-facing “verbatim adaptive session” switch. If you need exact search behavior, use direct search/play-search functionality rather than starting an adaptive session.

## Where Session Search Results Live

When a session plans a source, Vesper builds a **query pool** for that source:

```text
search source -> Apple Music lookup -> ordered candidate tracks -> in-memory query pool
```

A query pool contains:

- the source `{kind, term}`;
- optional resolved resource metadata, such as artist ID, genre ID, playlist ID, or resolved name;
- an ordered list of candidate tracks;
- a cursor;
- per-track state: `fresh`, `played`, `screened_out`, or `rejected`.

Important: full candidate pools are process-local runtime state. They are not stored in SQLite.

SQLite stores durable session data such as:

- sessions and steering history;
- selected session tracks;
- session events;
- minimal persisted runtime fields like active/suspended intent, last advance time, last selected track ID, and last known playback state;
- preferences.

Because candidate pools are not persisted, restarting the service can require rebuilding pools from the active session's request/steering rather than resuming the exact candidate list.

## Can You View the Search Results or Queue?

There are three different things people might call “the queue”:

1. **Cider's native queue** — visible through Vesper's `get_queue` action / `what is the queue?` if the resolver maps it there. This is Cider's playback queue.
2. **Session recent tracks** — selected session tracks persisted in SQLite and shown by `session_status`.
3. **Session candidate pools** — in-memory candidate lists used for future adaptive choices.

Currently, there is no stable public command that dumps the full in-memory session candidate pool. Candidate windows and pool summaries can appear in session debug logs if debug logging is enabled in code/config, but the user-facing status focuses on the active session and recent selected tracks.

This means: `get_queue` is not the same as “show me every candidate Vesper found for this session.” Vesper usually plays selected tracks directly rather than enqueueing the whole pool into Cider.

## What Happens After a Session Starts?

Starting a session does this:

1. stop/replace any previous active session;
2. create a new active session row in SQLite;
3. clear Cider's queue;
4. plan or seed a search source;
5. build an in-memory candidate pool;
6. show the resolver a small candidate window;
7. play the selected track directly through Cider;
8. record the selected track in SQLite;
9. keep the session active for later advances.

The session does **not** enqueue every candidate and play them in order.

Instead, each advance repeats the selection loop:

```text
active source pool
  -> next fresh sequential window, up to SESSION_SELECTION_WINDOW_SIZE
  -> resolver chooses selected_index, or -1 for none suitable
  -> chosen track is marked played and played directly
  -> if the whole window is unsuitable, it is marked screened_out
  -> cursor advances past the shown window
```

The pool itself is ordered by the Apple Music result/relationship order. Vesper walks it sequentially to create windows. The resolver chooses within each small window; it does not see the entire pool at once.

When no fresh tracks remain, Vesper may reset `screened_out` tracks first, then `played` tracks. `rejected` tracks are not reset inside the same pool.

## Mid-Session Steering

Steering means changing the future direction of an active session, for example:

- `prefer female vocalists`
- `more pop`
- `less sleepy`
- `keep it upbeat`
- `no more ballads`

The resolver should choose `steer_session` only when there is already an active session and the user wants to shape future picks.

When steering runs, Vesper:

1. appends the steering text to the session's persisted steering history;
2. normalizes an optional `search_update` from the resolver;
3. updates active search sources according to the mode;
4. records a `session_steered` event;
5. usually defers audible change until the next track.

`search_update.mode` can be:

| Mode | Meaning |
| --- | --- |
| `preserve` | Keep current active search sources. The steering text still affects future resolver choices because it is included in selection/planning context. |
| `add` | Add new typed sources alongside existing sources. |
| `replace` | Replace active sources and rebuild query pools for the new direction. |

For a request like `prefer female vocalists`, the resolver may simply preserve the current source and rely on the selection prompt to prefer matching candidates, or it may add/replace sources if it can express the steering as an `artist`, `genre`, or `vibe` source. The exact choice depends on resolver output.

Steering is cumulative. Resolver prompts tell the model to treat steering as persistent session state, not a one-turn hint, until explicitly overridden.

## Track Rejection vs. Steering

`i don't like this` / `reject current track` is different from steering.

When `reject_current_track` runs, Vesper:

- records the current track as `globally_rejected_track`;
- if a session is active, marks the current session track rejected and records a session event;
- immediately advances the session to a replacement track.

Steering changes future preferences; rejection says this specific current track should be avoided and replaced now.
