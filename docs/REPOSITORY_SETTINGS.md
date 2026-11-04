# Repository maintenance and remaining administrator-only settings

## Automated reliability checks

- **Curated U.S. (36):** a decoded-audio check runs daily. All diagnostics are
  saved as a run-specific artifact and the failure counters/playlist are
  published before a final **strict live-health gate**. An unhealthy station
  marks the GitHub Actions run red, even when its report was saved.
- **World Select (72):** the weekly audio audit exits unsuccessfully when any
  station fails its decoded-audio sample. The full report still uploads, and
  stations are not silently deleted because of a single outage.
- **U.S. directory:** the weekly source is crowd-maintained; it only publishes
  links with recent successful directory checks, no reported SSL error, HTTPS
  transport, acceptable URL structures, and no recognized token/expiry query
  parameters. An abnormal drop compared to the previous index stops
  publication instead of deleting thousands of entries.
- **World artwork:** the cover workflow generates only missing PNGs, retaining
  optimized custom covers, and publishes complete 512×512 station-specific
  files. All 72 world stations have cover references.

To verify playback in Primuse, refresh the relevant subscription and test sample
stations. A failed CI audio audit may indicate a transient outage; inspect the
report before changing a station identity or stream URL.

## Concurrency and publication

The two generated-data workflows now fetch and rebase on current `main`
before publishing and retry safe fast-forward pushes. Rebases involving
conflicting edits stop visibly rather than force-pushing or overwriting manual
edits. The artwork workflow uses the same policy for its branch.

## Repository settings

Repository administrators can configure the About section and branch rules:

- Repository → About → Description (suggested):
  `Live radio for Primuse: 36 curated U.S. stations, a refreshed U.S. directory, and 72 handpicked world stations in 44 countries.`
- Repository Settings → Rules → Rulesets: reviewed PRs and passing CI can be
  required for code changes after scheduled workflows are adapted to publish
  generated data (for example, through bot-created PRs).

Never publish a user token or remove the active non-fast-forward/deletion
rules just to make a workflow green.
