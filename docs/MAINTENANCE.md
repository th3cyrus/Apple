# Maintenance and publication

## Read a failed run

Download `stream-health-<run ID>-<attempt>` from Actions. It contains
`current-run.json`, including partial results if execution stopped. Match the run
ID and commit SHA, then inspect `status`, `fatal_error`, `summary`, each station's
`stream_check`, and its `candidates`/`candidate_checks` where applicable.

`complete_with_errors` means all stations were processed, with unexpected
station-level failures recorded for review. `failed` means a fatal error prevented
completion/publication. `running` in a finished job means only a checkpoint survived.
An empty or stale artifact is never evidence that the new execution was healthy.

For live testing without publication, select the workflow's `report_only` input,
or run `python scripts/update.py --refresh --report-only` locally. Local probes still
write diagnostics, but do not change the maintained catalog, playlist or covers.

## Review identity changes

Aliases and callsigns in `stations.json` describe the maintained channel. Verify
them against the broadcaster before editing. Do not add a generic network name to
make a rejected alternative pass. A verified UUID can strengthen identity, but
cannot override a conflicting band, frequency, channel, website, or health check.
Directory metadata is community-maintained and is not an authenticity guarantee.

## Update dependencies

`requirements.txt` pins both direct and transitive Python dependencies to the
versions tested with Python 3.12.16. Update the set together in a review branch,
install it in a clean environment, run all regression tests and offline validation,
then perform a report-only live check. Verify Action SHAs in each official
`actions/*` repository before updating them; keep the adjacent version comment.
The FFmpeg build comes from the Ubuntu runner/distribution and is not bit-for-bit
locked by Python requirements.

## Branch protection compatible with the refresh bot

The checked-in `main-ruleset.json` is the desired GitHub ruleset for `main`:
active deletion and non-fast-forward protection, with no bypass actors. Normal
fast-forward bot commits continue to work. Import/create it in repository
Settings → Rules → Rulesets when administrative access is available. Keeping this
file in Git does **not** activate the server-side setting; verify it in GitHub.

The CI workflow runs on pull requests, but this ruleset deliberately does not
require a PR or uncompleted status check on each generated data commit. Requiring
those checks for every direct push would block the current refresh bot. Stronger
code-review policies need a separate design for generated-data publication, such
as bot PRs, rather than a broad privileged-app bypass.

Publication stages only `stations.json`, `radio.m3u`, `logos/` and the health history.
The checkout stores no credentials. A short-lived askpass helper reads the job
token only during the final push and is removed afterward. Concurrent refreshes
are serialized; a non-fast-forward push fails visibly and should be rerun.
