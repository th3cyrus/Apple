# Repository maintenance and remaining administrator-only settings

## Automated reliability checks

- **Curated U.S. (36):** a decoded-audio check runs daily. All diagnostics are
  saved as a run-specific artifact and the failure counters/playlist are
  published before a final **strict live-health gate**. An unhealthy station
  marks the GitHub Actions run red, even when its report was saved.
- **World Select (71):** the weekly audio audit exits unsuccessfully when any
  station fails its decoded-audio sample. The full report still uploads, and
  stations are not silently deleted because of a single outage.
- **U.S. directory:** the weekly source is crowd-maintained; it only publishes
  links with recent successful directory checks, no reported SSL error, HTTPS
  transport, acceptable URL structures, and no recognized token/expiry query
  parameters. An abnormal drop compared to the previous index stops
  publication instead of deleting thousands of entries.
- **World artwork:** the cover workflow generates only missing JPG files.
  No separate SVG or PNG fallback artwork is distributed. All 71 world stations have high-resolution
  1254×1254 JPG-cover references.

To verify playback in Primuse, refresh the relevant subscription and test sample
stations. A failed CI audio audit may indicate a transient outage; inspect the
report before changing a station identity or stream URL.

## Concurrency and publication

The two generated-data workflows now fetch and rebase on current `main`
before publishing and retry safe fast-forward pushes. Rebases involving
conflicting edits stop visibly rather than force-pushing or overwriting manual
edits. The artwork workflow uses the same policy for its branch.

## Repository settings

Repository administrators can configure the About section and branch rules. The current GitHub About description still cites an older directory total; the suggested text below deliberately omits that changing figure:

- Repository → About → Description (suggested):
  `Live radio for Primuse: 36 curated U.S. stations, 71 world stations, 9 language playlists, a 12-part U.S. directory & custom JPG covers.`
- Repository Settings → Rules → Rulesets: reviewed PRs and passing CI can be
  required for code changes after scheduled workflows are adapted to publish
  generated data (for example, through bot-created PRs).

Never publish a user token or remove the active non-fast-forward/deletion
rules just to make a workflow green.
