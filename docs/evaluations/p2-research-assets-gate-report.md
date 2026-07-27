# P2 Research and Assets Gate Report

Date: 2026-07-27

## Result

- Full offline suite: 394 passed, 6 deselected.
- M1, M2, M3 and P1 automated gates: passed.
- P2 automated gate: passed from `artifacts/p2-research-assets/pytest.xml`.
- Online provider smoke checks: not part of the offline pass.
- Office checks: require the user's interactive Windows login session.

## Verified scope

- requirement analysis plans research without making a network call;
- factual search starts only after overview-outline approval;
- Openverse and Wikimedia responses preserve source, author and license;
- provider errors are reduced to safe categories and retries are bounded;
- every image URL and redirect passes SSRF validation;
- MIME, decoded format, byte size, dimensions and hash are verified before
  atomic publication;
- strict and loose license modes persist with project export/import;
- candidates are bound to project, Blueprint version and page;
- Blueprint approval rejects unapproved image references and unresolved image
  pages;
- Streamlit displays verified local thumbnails and persists selection.

## Manual acceptance

1. Use a current-information topic with `AUTO`; confirm no research request is
   sent before overview approval.
2. Approve the overview, run research with a Bocha key, inspect sources and
   exclude one fact.
3. Generate a Blueprint and confirm only photo/illustration pages search for
   images.
4. Select a candidate, refresh, and confirm the selection remains.
5. Test `LOOSE` mode and verify the author, source, license and warning.
6. Choose a no-image layout and confirm no placeholder is required.

## Residual risks

- Anonymous image APIs apply external rate limits and may be unavailable.
- License metadata is provider-supplied and cannot replace legal review.
- Image relevance still needs human acceptance.
- P3 must compile the approved asset into the actual PPTX and source footer.
