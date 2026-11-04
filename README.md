# Apple · Radio Collections for Primuse 📻

**Curated radio from the United States and around the world — ready to subscribe in [Primuse](https://github.com/chenqi92/primuse).**

Choose from **three separate M3U collections**: a carefully maintained U.S. selection with matching artwork, a large searchable-by-list U.S. directory, and an editorially selected international playlist. Subscribe to each collection independently; updating one does not import the others.

| Collection | Stations / Streams | What makes it different | Subscription |
| --- | ---: | --- | --- |
| **[U.S. Curated Radio](stations.json)** | **36 stations** | Handpicked broadcasters, matching custom covers, and decoded-audio health checks | **[Subscribe](https://raw.githubusercontent.com/th3cyrus/Apple/main/radio.m3u)** |
| **[U.S. Radio Directory](us-directory/README.md)** | **[Live station count](us-directory/index.json)** | Broad American coverage via Radio Browser, split into **12 M3U playlists** to respect Primuse's per-subscription limit | **[Choose playlists](us-directory/README.md)** |
| **[World Radio Select](world-radio/README.md)** | **72 stations · 44 countries/regions** | International music, news and culture; matching station covers and automated audio checks | **[Subscribe](https://raw.githubusercontent.com/th3cyrus/Apple/main/world-radio/radio.m3u)** |

**How to add a collection:** In Primuse, go to **Radio → + → Add Subscription → Fetch → Subscribe**. Choose **Update Now** to see changes made to an existing subscription.

**Editorial scope:** Quranic and Islamic religious programming is excluded from the World Radio Select and U.S. Directory collections.

**Playback and coverage:** The U.S. directory is community-sourced and is **not individually audio-tested**; its station count changes with [weekly refreshes](us-directory/index.json). The curated and world collections use audio-decoding checks, but even a successful test cannot guarantee access from every country or compatibility with every player. This repository hosts playlists and artwork, **not radio audio**.

[Explore station data](stations.json) · [World station list](world-radio/stations.json) · [U.S. maintenance status](https://github.com/th3cyrus/Apple/actions/workflows/import.yml) · [World audio audit](https://github.com/th3cyrus/Apple/actions/workflows/world-radio.yml)

---

## Get Primuse

- [Download Primuse on the App Store](https://apps.apple.com/us/app/primuse/id6761675450)
- [Primuse on GitHub](https://github.com/chenqi92/primuse)

No official Google Play release has been verified.

These M3U subscriptions may also work with other compatible radio players.

---

## Subscribe in Primuse

Open **Primuse → Radio → + → Add Subscription**, paste an M3U URL, tap **Fetch**
and **Subscribe**. You can enable **Update Automatically**, or choose
**Update Now** when changes in the GitHub files do not appear immediately in the app.

### Option A — Curated collection (36 stations)

Use the single subscription URL below. It includes the custom frosted-glass covers
and all 36 manually maintained station identities.

```text
https://raw.githubusercontent.com/th3cyrus/Apple/main/radio.m3u
```

### Option B — Expanded U.S. directory (12 playlists; [live count](us-directory/index.json))

Open **[U.S. Directory — 12 subscription URLs](us-directory/README.md)** and
subscribe to the parts you want **one at a time**. These lists are separate from
the curated collection: refreshing the curated subscription will **not** add them.

Primuse processes at most **1,000 entries per subscription**; the directory is
split into 12 files below the per-subscription limit. Each has a stable
subscription URL for updates. An additional [featured HTTPS preview](us-directory/featured.m3u)
contains a smaller, directory-derived selection.

The directory lists **candidates**, not individually playback-tested stations.
Some streams may be offline, silent, incompatible, region-restricted or duplicated
under different directory identities. The expanded lists use station favicons when safe HTTPS artwork is provided;
otherwise they use a project-owned fallback cover in the same visual style.
These directory covers are not verified official broadcaster trademarks.

### Option C — World Radio Select (72 stations)

Import [World Radio Select](world-radio/README.md) as a **separate subscription**. Every station has a matching cover; current audio-check reports are available in [GitHub Actions](https://github.com/th3cyrus/Apple/actions/workflows/world-radio.yml).

```text
https://raw.githubusercontent.com/th3cyrus/Apple/main/world-radio/radio.m3u
```

## Features

**Curated collection**

- 36 selected U.S. live radio stations, including Radio Paradise Rock Mix.
- Consistent custom frosted-glass cover artwork stored in `logos/`.
- Genre-organized M3U playlist with direct station stream URLs.
- Daily checks using FFprobe/FFmpeg to decode audio and flag silent or
  mislabelled streams, with conservative repair and diagnostics.
- Curated identity checks, manual locks, and original artwork preservation.

**Expanded U.S. directory**

- Thousands of U.S. HTTPS streams in 12 independent M3U playlists; the
  [live index](us-directory/index.json) has the current station count.
- Radio Browser-based discovery, filtering of known-bad entries and unsafe
  or misleading URL patterns, plus de-duplication by exact stream URL.
- Automatic weekly rebuilding, a JSON index of counts, and a smaller
  [featured playlist](us-directory/featured.m3u).
- **No per-station FFmpeg playback guarantee**; Radio Browser's recent
  check is directory metadata, not an independent audio-decoding test.

### Regional access and station identity

American broadcaster origin is **not** the same as U.S.-only access. The
curated station **WMMR 93.3 (US Only)** has a regional-access label. Other stations are
not marked U.S.-only without station-specific evidence.

**Radio Paradise Rock Mix** is a separate U.S. Internet music service, not a
rebroadcast of WMMR. It remains in the curated Rock & Alternative group.

Stream access may vary by network, provider, region and playback client.

### Expanded directory automation

The expanded lists are generated from **Radio Browser** and published to
[`us-directory/`](us-directory/README.md). Each currently has fewer than 1,000
entries, avoiding Primuse's per-subscription import limit. The
[`U.S. Radio Directory Refresh`](https://github.com/th3cyrus/Apple/actions/workflows/us-directory.yml)
workflow runs **weekly on Monday at 04:31 UTC** and can also be run manually.

If a directory fetch is incomplete or unexpectedly small, generation fails
rather than replacing published lists with truncated output. The curated
36-station playlist is never overwritten by the directory generator.

### Curated radio categories

- Hip-Hop & R&B
- Rock & Alternative
- Independent & Eclectic
- Jazz & Blues
- Classical
- News & Talk

## Automatic Updates

The **curated playlist** is checked daily at **03:17 UTC**.
The **expanded U.S. directory** is rebuilt every Monday at **04:31 UTC**.
Both are managed by separate GitHub Actions workflows and separate M3U files.
Relevant changes to the catalog, maintenance code, dependencies or refresh workflow
also trigger a refresh. Bot-generated data commits do not trigger another refresh.

To run manually, open [Primuse Radio Refresh](https://github.com/th3cyrus/Apple/actions/workflows/import.yml)
and select **Run workflow** on `main`. Enable **report_only** to check streams and
save diagnostics without publishing catalog, playlist or artwork changes.

### Audio Verification

A successful HTTP response alone is not considered healthy. The checker reads a
bounded sample, uses **FFprobe** to identify audio packets, and then uses **FFmpeg**
to decode PCM and measure its signal level. Silent, undecodable or mislabeled
audio is flagged instead of being marked healthy. Audio/playlist double-extension
URLs (for example `.mp3.m3u`) are never accepted. The probe
resolves M3U/PLS entries and HLS master/media playlists, checks a media segment,
and supports HLS initialization segments. No station is removed for failing a check.

The probe uses 5-second connect and 12-second read timeouts, a 45-second overall
processing budget, up to 3 attempts with 1- and 2-second delays, at most 5 redirects
per resource, 3 playlist levels, 64 KiB playlists and up to 128 KiB media samples
(with a separate 8-second streaming read cap).
Socket/DNS behavior can exceed application time checks; the refresh job has a hard
20-minute cap. The script stops starting station work after 15 minutes. A small
verified sample does not prove uninterrupted playback, the correct station identity,
or compatibility with every device/player. Very quiet samples may need manual
review; encrypted or unrecognized media also requires manual review.

Transient timeouts, connection errors and HTTP 408/429/500/502/503/504 can be retried.
403 responses, TLS errors and unverified media do not authorize automatic URL
replacement. Temporary or region-dependent failures require review.

### Conservative Stream Repair

Healthy or manually locked URLs never trigger a directory lookup. An eligible
repair requires **three consecutive counted failures at least 24 hours apart**;
multiple retries and manual runs on the same day cannot accelerate the counter.
Successful checks reset it. Legacy counters without timestamps restart under this
policy. With only daily runs, eligibility is normally reached about 48–72 hours
after an outage starts; a valid replacement may still be unavailable.

`stations.json` includes editable `identity` metadata: reviewed aliases, callsigns,
frequency where explicit in the catalog, band and program channel. Directory
names must match this identity and the broadcaster website; AM/FM, HD subchannels,
frequency and WRTI Jazz/Classical conflicts block replacement. UUID allowlists are
optional and must be independently verified; none are invented automatically.

The Radio Browser client discovers mirrors, falls back to DNS/known hosts and
quarantines failed mirrors for the current run. A valid empty response is not
retried on other mirrors. Multiple hostnames can point to the same physical service.

All returned candidates are filtered for identity, U.S. metadata, website, URL/TLS
safety and a positive directory check within 14 days **before ranking**. Up to
three HTTPS alternatives are checked live, with one additional HTTP fallback
reserved if needed (or up to three HTTP options when no HTTPS is eligible). A rejected or unavailable first
candidate does not hide the next one.

**HTTPS is preferred; HTTP remains permitted as a fallback.** Secure candidates
are checked before HTTP candidates. If an HTTPS URL traverses HTTP, that transport
is also treated as a fallback while other secure candidates are considered. All
request hops, including playlist/segment URLs, record protocol use. Public reports
redact URL queries and credentials. HTTP is unencrypted and may be rejected by
some players/platforms.

### Stream Health Diagnostics

- `logs/current-run.json`: checkpointed results for this execution; ignored by Git.
- `logs/stream-health.jsonl`: the latest 30 finalized complete or failed executions.
- Actions artifact `stream-health-<run ID>-<attempt>`: only that execution's report,
  retained for 90 days; it never packages an old history file as a fresh report.

Reports identify the run, attempt, code commit, expected/checked station counts,
per-request status/timing/bytes, detected codecs, candidate rejections and HTTP use.
Results are saved before/after each station. Station-specific exceptions are
recorded and processing continues. Fatal errors save available results and a
sanitized traceback. Abrupt termination can leave a `running` checkpoint; it is
explicitly partial. Validation checks report ownership and completeness before
publication. Writes use temporary files and atomic replacement.

The Actions summary displays counts even when the refresh fails after starting.
A successful workflow can include stations marked `needs_review`; read the summary
and report instead of treating the green badge as an all-stations guarantee.

### Local Checks and Regression Tests

Use Python 3.12 and install FFmpeg/FFprobe, then run:

```sh
python -m pip install --only-binary=:all: -r requirements.txt
python -m unittest discover -s tests -v
python scripts/validate.py
python scripts/update.py --refresh --report-only
```

Tests include real local HTTP responses and bounded audio samples, failed HLS
segments, candidate ranking/identity, failure spacing, locked streams, per-station
isolation, atomic writes and partial/fatal reports. They do not require public
radio services. CI runs on relevant pushes and pull requests with read-only
permissions, and validates the catalog, all covers and playlist ordering.

The project workflows use `ubuntu-26.04`, Python `3.12.16`, pinned Python
dependencies and commit-pinned GitHub Actions. Curated and directory refreshes
run as separate jobs; publication credentials are used only for publishing.
The directory publisher fetches and rebases on the current main branch before
pushing, while the curated refresh aborts on conflicting remote changes.

### Manual Stream Repair

If a station stops working:

1. Open `stations.json`.
2. Locate the affected station.
3. Update its `stream` URL.
4. Commit the changes.
5. Run the refresh workflow.
6. Select **Update Now** in Primuse.

---

## Repository Structure

| Path | Description |
| --- | --- |
| `stations.json` | Editable catalog of 36 radio stations |
| `radio.m3u` | Main curated M3U subscription (36 stations) |
| `world-radio/` | Standalone world playlist, country catalog and station covers |
| `scripts/generate_world_covers.py` | Reproducible project-style cover generation for world stations |
| `.github/workflows/world-artwork.yml` | Automatically fill in missing world station cover PNGs |
| `us-directory/us-01.m3u` … `us-12.m3u` | Twelve expanded U.S. directory subscriptions |
| `us-directory/index.json` | Current directory totals and per-playlist counts |
| `us-directory/README.md` | All expanded directory subscription URLs |
| `us-directory/featured.m3u` | Small featured HTTPS directory preview |
| `scripts/build_us_directory.py` | Filter, deduplicate and split the expanded U.S. directory |
| `.github/workflows/us-directory.yml` | Weekly/manual directory regeneration and publishing |
| `logos/` | Original station cover artwork |
| `scripts/update.py` | Maintenance orchestration and atomic playlist generation |
| `scripts/stream_probe.py` | Decoded audio, silence detection, playlist handling, retries and HTTP diagnostics |
| `scripts/identity.py` | Broadcaster and program-channel matching |
| `scripts/catalog.py` | Station schema validation before processing |
| `scripts/health_report.py` | Per-run checkpoints and bounded history |
| `scripts/validate.py` | Shared offline output/report validation |
| `scripts/radio_browser.py` | Mirror discovery, failover and catalog search |
| `tests/` | Offline directory builder, media and maintenance regression tests |
| `logs/stream-health.jsonl` | Last 30 finalized stream reports |
| `logs/current-run.json` | Current execution checkpoint (not committed) |
| `docs/MAINTENANCE.md` | Dependency updates, diagnostics and branch rules |
| `.github/workflows/import.yml` | Scheduled and manual radio refresh workflow |
| `README.md` | Project documentation |
| `LICENSE` | MIT License for original project code |
| `ARTWORK_LICENSE.md` | CC BY 4.0 terms and third-party rights for custom covers |

---

## Station Artwork

All **36 curated station covers** feature a consistent, minimalist design inspired
by frosted glass, soft gradients, and clean typography. This includes the updated
Radio Paradise Rock Mix artwork.

The **expanded directory** uses third-party favicon links when available; those
thousands of stations are not covered by this custom visual design.

The artwork is hosted directly in this repository and is designed to provide a consistent appearance across the radio collection.

Station names are used for identification. They do not imply affiliation with or endorsement by the broadcasters.

Existing custom artwork is preserved during scheduled playlist refreshes.

---

## Playback Notes

Radio streams are provided by third-party broadcasters.

Playback availability may vary due to:

- Temporary broadcaster outages
- Geographic restrictions
- Stream URL changes
- Network connectivity issues
- Server-side HTTP errors

A successful playlist download does not guarantee uninterrupted playback of every station.

If a station returns an HTTP error, check its official website before replacing the stream URL.

HTTPS certificate verification should remain enabled.

---

## License

Original project code and project-authored documentation are released under the [MIT License](LICENSE), subject to the terms in that file.

The original creative elements of the custom station covers are made available under [CC BY 4.0](ARTWORK_LICENSE.md), to the extent that the maintainer controls the relevant rights. Attribution is required under that license. AI-generated elements may not qualify for copyright protection in every jurisdiction.

Station names, trademarks, broadcaster audio, and third-party content remain subject to their respective owners' rights.

Neither license grants permission to use third-party trademarks or redistribute copyrighted broadcasts.

---

## Disclaimer

**Apple · Radio Collections for Primuse** is an independent, community-maintained radio playlist project.

It is not affiliated with, sponsored by, or endorsed by:

- Apple Inc.
- Primuse or its developers
- Any featured radio station or broadcaster

This repository provides station metadata and links to broadcaster or third-party
audio streams. It does not host or rebroadcast the audio, and does not promise
that directory-listed streams are available in every country.

---

Made for radio listeners.
