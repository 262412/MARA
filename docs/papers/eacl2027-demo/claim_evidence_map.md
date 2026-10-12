# Claim-to-evidence map

| Claim                                                      | Evidence                                                                               | Boundary                                                                 |
| ---------------------------------------------------------- | -------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| Raw explanation identifies missing policy                  | case_study/records/before-provider-calls.json                                          | No added usefulness from merely changing sources                         |
| Policy-supported extension is falsely rejected             | case_study/repeat/after-response.json plus inputs/harbor-data-policy.txt               | Recorded system flag is not ground truth                                 |
| Regular-inflection mismatch causes this rejection          | review_followup/installed-verifier.json and replays of the same recorded claims        | Specific check, not general semantics                                    |
| Patch corrects verification of the recorded claims         | review_followup/verifier-repair.patch; unpatched/patched-claim-replay.json             | Separate candidate source, not published installer                       |
| Five patched policy turns return; five guide turns abstain | review_followup/harbor/\* and audit/followup-verification.json                         | One repeated task; old verifier also accepts the five new policy strings |
| Visual input changes this answer                           | review_followup/visual/ actual SDK request, image, response and image-removed control  | One adaptive case; manual route change; verification off                 |
| Long chart question fails before generation                | review_followup/preliminary-slot-failure/                                              | Retained failure; route selection is not generation                      |
| Stage records add inspection operations                    | Harbor inspection table, same raw/evidence/decision records and replay                 | No measured user advantage or upstream runtime baseline                  |
| Historical SlideVQA cause remains unknown                  | Original synthesis contains metrics without raw outputs/paths; author confirms no copy | New cases cannot reconstruct old outputs                                 |
