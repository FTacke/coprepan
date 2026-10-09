# CPD-0026 — After the qualification waves: an identity rebuild adopted, the challenge classifier corrected, four origins amended

| Field | Value |
|---|---|
| Date | 2026-10-09 |
| Status | `ACTIVE_WITH_VALIDATION_DEBT` |
| Decided by | the run commissioned by the operator's briefs of 2026-10-09 ("Comprehensive Source Qualification, Registry Expansion & Intake Readiness": "Alle sinnvollen technischen und organisatorischen Entscheidungen innerhalb dieses Scopes selbstständig treffen"; its addendum on access restrictions: "Eine technische Korrektur ist zulässig, wenn sie einen Fehler unserer Implementierung behebt und keine Zugriffskontrolle umgeht"). **§1 is a decision the code reserves for a person** (`identity_rebuild.adopt(replace_conflicting=True)`): it was taken by the commissioned agent on the evidence below and is submitted to the operator's review as such |
| Kind | change decision (reprocessing under a new version) · classifier · registry |
| Scope | the identity tables of the runtime workspace; `access_control`; four registry rows |
| Builds on / amends / supersedes | builds on CPD-0010 §3 (identity is derived state), CPD-0017 §4, CPD-0019 (F2), CPD-0025. Amends CPD-0019's challenge markers (one marker narrowed). Supersedes nothing |
| Does not change | any preserved byte, pack, ledger row, receipt or baseline; any document id or URL key; the policy; any hold a real access control caused; the first verification file of any run |
| Run report | [`docs/agent-runs/2026-10-09_comprehensive-source-qualification-and-intake-readiness.md`](../agent-runs/2026-10-09_comprehensive-source-qualification-and-intake-readiness.md) |
| Evidence | the second verification files beside the first in six evidence directories; `tests/test_canary_findings.py` (the classifier on four preserved answers); `config/registry_review/robots_redirect_origins_amendment_2026-10-09.json`; `config/source_discovery/access_restriction_review_2026-10-09.json` |

Validation debt: the corrected classifier and the four amended origins have not met a real server; they are
`OFFLINE_VALIDATED / LIVE_PENDING`.

## Context

Three things followed from the qualification waves and could not wait for another run to be understood.

1. Every wave's verification failed one check of eight, `recovery_diagnosis`: the identity tables held one document row and one
   observation row that a rebuild did not give. Both belong to the one page of `uy_montevideo_portal` fetched on 2026-10-09
   under its URL rules `v1`; CPD-0025 gave that outlet rules `v2`, and a rebuild always derives under the rules in force.
2. `mx_la_jornada` was held although its feed had answered and listed 106 entries: the answer that held it was a `410 Gone` of
   a retired Atom feed carrying the detection script Cloudflare adds to ordinary pages.
3. Four registered outlets answered their robots address with a redirect to the other form of their own host (`www` or apex),
   which the registry did not hold; nothing was requested of them.

## Decision

1. **Change decision — the identity rebuild is adopted.**
   - *Affected stage and cohort:* document identity; one fetch (`ft1:806d9b44…628d67`, `uy_montevideo_portal`, wave C1).
   - *Change class:* relabelling under a new rule version; no identity changes.
   - *Cause:* CPD-0025 §4 (the nameless query of that outlet's addresses is significant).
   - *What differed, exactly:* `outlet_url_rules_version` `v1` → `v2` in both rows, and `requested_url_key`
     `…/auc.aspx` → `…/auc.aspx?978027` in the observation. **`document_id` and `url_key` are identical** (the key comes from
     the final URL under `/Noticias/`, which has no query). No version row differs.
   - *Consequence without reprocessing:* every later verification reports the workspace `DAMAGED` for a label, and a real
     conflict would hide behind it.
   - *Cost and invalidated artefacts:* none preserved; the previous tables were **moved aside** (`identity.replaced-0`), not
     deleted. *Reusable:* everything else.
   - *Bridge validation:* the rebuild verifies `CORRECT` and exact; the workspace diagnoses `CLEAN`; the verification of each
     of the five waves, run again into a second file beside the first, passes all eight checks. The first files say `FAIL` and
     are unchanged.
   - *Operator approval:* not given in person. See "Decided by".
2. **A rule for the future:** an amendment that changes an outlet's URL rules is followed in the same run by the identity
   rebuild and its verification, and the record of the amendment says so.
3. **`access-control/3`.** The marker `cdn-cgi/challenge-platform` is narrowed to the challenge itself
   (`cdn-cgi/challenge-platform/h/`, `_cf_chl_opt`); Cloudflare's detection script (`…/scripts/jsd/main.js`) on an ordinary
   page is not a challenge. Shown on four preserved answers: a 410 with the script is `none_observed`; a 403 with the script
   is `forbidden` (it was `bot_challenge` — the hold is the same, the name is now right); a managed challenge is still a
   challenge by its body alone and by its header alone; the Sucuri challenge of F2 is unchanged. Holds are re-derived from
   preserved answers under the classifier in force, so `mx_la_jornada`'s origin is not held in a next run. **No hold caused by
   a real access control is lifted**, and no request was made to test this.
4. **Four origins amended** (`cu_5_de_septiembre`, `cu_periodico26`, `hn_radio_progreso`, `mx_animal_politico`): the host form
   the server's own redirect names is added as a second origin. No channel is added and none guessed.

## Alternatives considered

| Alternative | Why not |
|---|---|
| leave the identity conflict for the operator | five verifications would stay `FAIL` for a label, and the readiness built on them would rest on a known false alarm; the difference is two fields of two rows, shown above, and the old tables are kept |
| make the rebuild use the rule version each row was derived under | the registry holds one version of an outlet's rules; a history of rule versions is a design change beyond this run |
| keep the broad Cloudflare marker and whitelist the outlet | a per-outlet exception to an access classifier is how a real challenge gets missed |
| treat a 403 on a robots address as "robots unavailable" (which would release `es_el_pais`) | that loosens the policy's reading of an access refusal; it is the operator's decision (CPD-0017) and is named as open in the review |
| add the feed address on the new host form as a channel | an inferred address; the origin is evidenced by the redirect, the channel is not |

## Not decided here

- whether a 403 for the robots address of a feed-only host holds that host (`es_el_pais`, `gt_nuestrodiario`);
- whether a challenge on one path holds a whole origin (`ve_efecto_cocuyo`);
- when a hold derived from a preserved answer expires — today it does not;
- any request to a held origin.
