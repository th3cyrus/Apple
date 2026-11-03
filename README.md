# Apple · USA Live Radio for Primuse 📻

A curated collection of **35 live U.S. radio stations**, featuring original minimalist artwork, an M3U playlist, and automated maintenance through GitHub Actions.

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

- **35 curated U.S. radio stations**
- Original minimalist frosted-glass-style station covers
- Self-hosted artwork for all 35 stations
- Ready-to-use M3U subscription playlist
- Stations organized by music genre
- Editable station catalog and stream URLs
- Automated weekly maintenance via GitHub Actions
- Manual workflow execution when needed

### Radio Categories

- Hip-Hop & R&B
- Rock & Alternative
- Independent & Eclectic
- Jazz & Blues
- Classical
- News & Talk

---

## Automatic Updates

GitHub Actions is configured to run every **Wednesday at 03:17 UTC**.

Manual updates are also available:

1. Open [Primuse Radio Refresh](https://github.com/th3cyrus/Apple/actions/workflows/import.yml).
2. Select **Run workflow**.
3. Keep the `main` branch selected.
4. Confirm the workflow execution.

The maintenance script:

- Checks station stream availability and records HTTP status codes, timeouts, TLS, DNS and content-type failures.
- Saves the latest 30 stream health reports in `logs/stream-health.jsonl` and uploads each refresh report as a GitHub Actions artifact for 90 days.
- Cautiously repairs outdated stream URLs when suitable alternatives are verified.
- Regenerates the M3U playlist.
- Preserves existing custom station artwork.
- Validates station records, cover files, and M3U playlist structure before committing.
- Commits updated files when changes are detected.

### Stream Health Diagnostics

On every refresh, `logs/stream-health.jsonl` records one JSON object per run. Read the last line for the newest station checks, including failure type, HTTP status, content type, response time and each Radio Browser mirror attempt. For stream checks, the `stream_check.attempts` array also records each individual request, its timing, HTTP status or exception. Older runs are trimmed to the most recent 30.

To download the same log from the Actions interface, open the workflow run and download its `stream-health-<run ID>` artifact (90-day retention). A single unreachable station is recorded as `needs_review` rather than failing the workflow.

Temporary stream errors (connection/read timeouts and HTTP 408, 429, 500, 502, 503, 504) are retried at most **two** times after the initial request, with short 1- and 2-second delays. Connect timeout stays at 5 seconds; read timeout is 12 seconds per attempt. Permanent responses such as 403/404, unexpected content types, and TLS certificate errors are not retried. A complete probe counts as one station check and cannot increment `fail_count` more than once, no matter how many requests were attempted.

### Radio Browser Reliability

The script checks each stream **before** consulting Radio Browser. A healthy
stream remains unchanged and does not cause a catalog lookup. For a failed
stream, the directory client obtains the available mirror list from Radio
Browser and falls back to DNS discovery and known hosts if needed. Faulty
mirrors are skipped for the remainder of that refresh run. Multiple DNS names
may resolve to the **same** physical service and do not guarantee independent
redundancy.

A replacement must meet all safeguards: a confident name match, the same
broadcaster's website, U.S. station metadata, a recent (within 14 days)
positive directory health check, no reported SSL error, HTTPS, three
consecutive failed checks of the old URL, and a successful live check of the
proposed URL. Manually locked streams are never automatically replaced.
Radio Browser is community maintained, so these checks reduce risk without
guaranteeing correctness or availability.

Offline regression tests live in `tests/test_radio_browser.py` and are run
on relevant pushes and before the scheduled refresh. Both workflows run on the
pinned `ubuntu-26.04` image. Refresh diagnostics are uploaded with
`actions/upload-artifact@v7`.

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
| `stations.json` | Editable catalog of 35 radio stations |
| `radio.m3u` | Public M3U subscription playlist |
| `logos/` | Original station cover artwork |
| `scripts/update.py` | Stream and playlist maintenance script |
| `scripts/radio_browser.py` | Mirror discovery, failover and catalog search |
| `tests/test_radio_browser.py` | Radio Browser regression tests |
| `logs/stream-health.jsonl` | Last 30 detailed stream diagnostics (created on next refresh) |
| `.github/workflows/import.yml` | Scheduled and manual radio refresh workflow |
| `README.md` | Project documentation |
| `LICENSE` | MIT License for original project code |
| `ARTWORK_LICENSE.md` | CC BY 4.0 terms and third-party rights for custom covers |

---

## Station Artwork

All 35 station covers feature a consistent, minimalist design inspired by frosted glass, soft gradients, and clean typography.

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
