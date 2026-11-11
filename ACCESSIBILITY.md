# Accessibility statement

Our target is SI 5568 level AA, with additional WCAG 2.2 A/AA automated coverage.
No complete SI 5568/WCAG conformance audit has been completed.

## Evidence

The pinned repo-checks action tests all catalog languages on the calculator,
guide and sources pages in Chromium and WebKit at 1280x900 and 390x844. The
project runner also scans a calculation using invented consumption intervals.
With the current six languages this covers 72 initial and 24 calculation states.
The shared action repeats the calculator/guide subset as a consumer integration
check. The runner emits counts and rule IDs, not page content.

The preview removes only the exact analytics tag, binds to 127.0.0.1, and replaces
the guide screenshots with synthetic images at the original dimensions. Production
analytics and tariff data are unchanged. Screenshot contents and hotspot overlays
on actual screenshot pixels are not covered by this preview. The guardrails are
for first-party synthetic/no-secret previews, not network isolation. Unsupported
browser network paths remain outside this contract.

## Known limits

Manual keyboard, screen-reader, zoom/reflow, focus, RTL and real-device checks
remain open. WebKit on Linux is not iOS Safari. Automated results and two browser
engines do not certify legal compliance or native two-OS coverage. Machine-draft
languages still need native-speaker review. Chart alternatives and non-text
contrast need manual review; numeric plan values are available in the table.

## Feedback

Report barriers and reproducible steps through the repository Issues page:
https://github.com/reihlinstinct/electricity-plan-calculator/issues
Do not include real consumption exports, account identifiers or other private data.
