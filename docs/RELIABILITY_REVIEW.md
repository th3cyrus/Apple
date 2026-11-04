# Reliability review — 2026-11-04

This review covers the maintenance scripts, six Actions workflows, published
catalogs/playlists and artwork. It records the checks performed on this date;
it is not a guarantee of future broadcaster availability.

## Corrections

| Finding | Result |
| --- | --- |
| The featured directory preview was never rebuilt, retaining obsolete entries after source filtering | Generate the top 100 eligible entries during every build and verify exact membership in the published shards |
| Directory output had no complete offline integrity check | Validate all 12 shard counts, total count, unique stream URLs, HTTPS/editorial policy and the preview |
| World playlist validation ignored incorrect cover URLs | Require the complete EXTINF metadata to match the catalog |
| Language artwork URLs could contain embedded credentials | Apply the shared URL validator before accepting artwork metadata |
| Signed/expiring links passed inconsistent checks, especially empty token values | Share query validation across world/language catalogs, directory generation and automatic repair candidates |
| Long directory artwork URLs were silently truncated | Preserve the full validated URL |
| FFmpeg decoding lacked the probe's protocol isolation and output duration bound | Allow only supplied pipe data and at most eight seconds of decoded PCM |
| Automatic artwork runs restyled existing covers despite the preservation policy | Generate missing files only; keep explicit local restyling available |
| Artwork CLI ignored the selected input directory and verification could create a file | Use the selected catalog/root and make verification read-only |
| Data/cover/shared-code changes could miss relevant CI checks | Cover every collection in offline CI and include shared probe/filter/dependency changes in live audit triggers |
| World/language reports discarded detailed transport diagnostics | Save the complete probe result using atomic report writes |
| Composite religious station names escaped the editorial filter | Include the filter changes proposed in PR #10 and rebuild the directory under that policy |
| KCSM's maintained URL differed from its official HD1 player's stream | Use the official, successfully decoded MP3 endpoint and clear the old failure counter |

KCSM's official [player](https://www.kcsm.org/) identifies HD1/Jazz 91 at
`https://ice7.securenetsystems.net/KCSM2`; it decoded eight seconds of audible MP3
in the verification sample.

## Verification

- 114 offline regression tests passed, including 14 new review regressions.
- Curated U.S.: 36 catalog entries and matching playlist/cover references validated.
- World Select: 72 entries validated; all 68 generated covers and four shared
  original U.S. cover references checked.
- Languages: nine playlists, 83 entries and their station PNGs validated.
- Directory: 3,967 filtered entries across 12 bounded shards, plus a regenerated
  100-entry preview; these directory streams were not individually audio-tested.
- All six workflow YAML files and 28 embedded shell steps parsed successfully.
- Python compilation, pinned dependency consistency and Git whitespace checks passed.
- The initial live sweep covered 158 distinct curated/world/language stream URLs;
  154 decoded successfully. Shared station URLs were tested once.

## Upstream playback failures requiring review

These are live service failures, distinct from the code defects corrected above.
No station identity was changed to conceal a failed audit, and strict live gates
remain enabled.

| Station | Observed result |
| --- | --- |
| KISW 99.9 | HTTP 503 from the maintained HLS service |
| RTBF Classic 21 | HTTP 502 from the maintained stream |
| RTBF Musiq3 | HTTP 502 from the maintained stream |
| Gensokyo Radio | HTTP 401 from the broadcaster-listed public endpoint |

RTBF publishes [new permanent stream entry points](https://support.rtbf.be/hc/fr-fr/articles/16393535008401-Liens-URL-des-cha%C3%AEnes-radio-et-webradios)
for Classic 21 and Musiq3. Those alternatives also failed this environment's
decoded-audio checks (timeout/HTTP 502), so unverified replacements were not
published. Gensokyo's [official endpoint list](https://stream.gensokyoradio.net/)
still lists the existing public MP3 stream; its public mobile/enhanced alternatives
also returned 401 in this check. A future successful bounded sample may resolve a
transient failure; current Actions artifacts remain the source for later runs.
