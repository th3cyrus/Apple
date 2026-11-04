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
fast-forward bot commits continue to work. It is active as
[Ruleset 26472586](https://github.com/th3cyrus/Apple/rules/26472586), targeting
`refs/heads/main`. If recreating the repository, import/create it in Settings →
Rules → Rulesets. Keeping the JSON file in Git alone does **not** activate a
server-side setting.

The CI workflow runs on pull requests, but this ruleset deliberately does not
require a PR or uncompleted status check on each generated data commit. Requiring
those checks for every direct push would block the current refresh bot. Stronger
code-review policies need a separate design for generated-data publication, such
as bot PRs, rather than a broad privileged-app bypass.

The curated refresh publishes only `stations.json`, `radio.m3u`,
`logos/` and the bounded health history. The U.S. directory publishes
`us-directory/` independently; world artwork generation fills only missing
`world-radio/logos/` images and the directory's shared cover. These workflows
use distinct concurrency groups to avoid cancelling one another. Before
publishing, they fetch and rebase against the latest target branch and retry
fast-forward pushes. A real content conflict still fails visibly and requires
review; force pushes are never used. Checkouts do not persist Git credentials:
short-lived askpass helpers access the job token only during publication.

The last step of curated refresh is a strict live-health gate: if any station
needs review, the workflow status is red **after** saving the audio diagnostic
artifact and preserving the state required for future repair. The weekly world
audit uses the same strict failure signaling and always uploads its detailed
report. An audit failure must not automatically remove radio stations.

Directory generation rejects reported SSL errors, tokenized/signed URLs and
stale Radio Browser health dates, and blocks publication when the number of
surviving streams unexpectedly drops. Directory links remain less thoroughly
verified than the curated and world playlists; CI observations describe the
runner environment only.

Every directory build also regenerates the 100-entry featured preview from the
same filtered candidates. Offline validation checks shard counts, duplicate URLs,
HTTPS/editorial policy and exact preview membership. All collection data and cover
changes trigger the offline integrity workflow; shared probe, filter and dependency
changes also trigger the relevant live audits. World/language reports preserve the
full probe diagnostics, including redirect hops, transport and decoded audio levels.

Scheduled artwork generation fills missing covers without restyling existing ones.
Use `--restyle` only for an intentional visual update. `--verify` is read-only;
`--directory` selects both the input world catalog and its output artwork directory.

For current visual coverage and administrative limitations, also read
[Repository Settings](REPOSITORY_SETTINGS.md).
