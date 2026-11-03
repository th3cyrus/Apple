# Apple · USA Live Radio for Primuse 📻

A curated collection of **36 live U.S. radio stations**, featuring original minimalist artwork, an M3U playlist, and automated maintenance through GitHub Actions.

[**Listen / Subscribe**](https://raw.githubusercontent.com/th3cyrus/Apple/main/radio.m3u) · [Browse Stations](https://github.com/th3cyrus/Apple/blob/main/stations.json) · [Workflow Status](https://github.com/th3cyrus/Apple/actions/workflows/import.yml)

---

## Get Primuse

- [Download Primuse on the App Store](https://apps.apple.com/us/app/primuse/id6761675450)
- [Primuse on GitHub](https://github.com/chenqi92/primuse)

No official Google Play release has been verified.

The M3U playlist may also work with other compatible radio players.

---

## Subscribe

1. Open **Primuse → Radio → + → Add Subscription**.
2. Paste the following URL:

   `https://raw.githubusercontent.com/th3cyrus/Apple/main/radio.m3u`

3. Tap **Fetch**, then **Subscribe**.
4. Enable **Update Automatically** to keep the station list synchronized.

You can also tap **Update Now** to refresh the subscription manually.

---

## Features

- **36 curated U.S. radio stations**
- Original minimalist frosted-glass-style station covers
- Self-hosted artwork for all 36 stations
- Ready-to-use M3U subscription playlist
- Stations organized by music genre
- Editable station catalog and stream URLs
- Automated daily maintenance via GitHub Actions
- Manual workflow execution when needed

### Region restrictions

The collection features U.S. stations, but this does **not** mean that every
stream is restricted to listeners in the United States. The WMMR 93.3 entry
carries the user-requested label **US Only** following a listener's
out-of-country permission-denied playback error. That does not independently
prove a worldwide US-only policy. Other entries are not labeled without
station-specific evidence; successful GitHub Actions stream tests do not prove
playback availability in every country.

Radio Paradise Rock Mix is an additional, independent American Internet music
service, not a rebroadcast of WMMR. Its direct MP3 link is kept in the catalog
without replacing WMMR.

### Radio Categories

- Hip-Hop & R&B
- Rock & Alternative
- Independent & Eclectic
- Jazz & Blues
- Classical
- News & Talk

---

## Automatic Updates

GitHub Actions checks the collection every **day at 03:17 UTC / 06:17 Iraq time**.
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

Both workflows use `ubuntu-26.04`, Python `3.12.16`, exact Python dependency
versions and verified commit SHAs for Actions (checkout v5, setup-python v6,
upload-artifact v7). Refresh publication uses credentials only in its final step;
concurrent runs are serialized and a conflicting push fails instead of overwriting
someone else's changes.

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
| `radio.m3u` | Public M3U subscription playlist |
| `logos/` | Original station cover artwork |
| `scripts/update.py` | Maintenance orchestration and atomic playlist generation |
| `scripts/stream_probe.py` | Audio packets, playlists, retries and HTTP diagnostics |
| `scripts/identity.py` | Broadcaster and program-channel matching |
| `scripts/catalog.py` | Station schema validation before processing |
| `scripts/health_report.py` | Per-run checkpoints and bounded history |
| `scripts/validate.py` | Shared offline output/report validation |
| `scripts/radio_browser.py` | Mirror discovery, failover and catalog search |
| `tests/` | Offline directory, media and maintenance regression tests |
| `logs/stream-health.jsonl` | Last 30 finalized stream reports |
| `logs/current-run.json` | Current execution checkpoint (not committed) |
| `docs/MAINTENANCE.md` | Dependency updates, diagnostics and branch rules |
| `.github/workflows/import.yml` | Scheduled and manual radio refresh workflow |
| `README.md` | Project documentation |
| `LICENSE` | MIT License for original project code |
| `ARTWORK_LICENSE.md` | CC BY 4.0 terms and third-party rights for custom covers |

---

## Station Artwork

All 36 station covers feature a consistent, minimalist design inspired by frosted glass, soft gradients, and clean typography.

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

**Apple · USA Live Radio for Primuse** is an independent, community-maintained radio playlist project.

It is not affiliated with, sponsored by, or endorsed by:

- Apple Inc.
- Primuse or its developers
- Any featured radio station or broadcaster

This repository provides playlist metadata and links to publicly accessible radio streams. It does not host or redistribute the broadcast audio.

---

Made for radio listeners.
