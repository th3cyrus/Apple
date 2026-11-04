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

For playback on your own network and device, use Primuse **Update Now** and
verify a few stations from each playlist. CI from a cloud runner cannot
guarantee access from every country. A red audio audit can also represent a
temporary station outage; inspect the report before changing an identity or URL.

## Concurrency and publication

The two generated-data workflows now fetch and rebase on current `main`
before publishing and retry safe fast-forward pushes. Rebases involving
conflicting edits stop visibly rather than force-pushing or overwriting manual
edits. The artwork workflow uses the same policy for its branch.

## GitHub About — manual repository setting

The connected GitHub integration cannot edit repository metadata or the
active ruleset. The following owner-only changes **have not been applied**:

- GitHub repository → About (gear icon) → Description:
  `Live radio for Primuse: 36 curated U.S. stations, a refreshed U.S. directory, and 72 handpicked world stations in 44 countries.`
- Repository Settings → Rules → Rulesets: the active main-branch ruleset
  currently prevents deletion and non-fast-forward updates. It does not
  require PR reviews or passing CI. Enforcing PR-only changes without
  accounting for data-publishing GitHub Actions would block the scheduled
  playlist bot. Separate bot-generated data publishing from protected code
  changes (e.g. use bot PRs) before enabling those rules.

Never publish a user token or remove the active non-fast-forward/deletion
rules just to make a workflow green.
