# Operations notes (Chapter 8)

Production observability for VaultLog is defined in
[ADR 0009](adr/0009-hardening-and-pipeline-controls.md). Before go-live (Chapter 9):

- Create log-based alerts for the signals listed in ADR 0009.
- Schedule `scripts/verify_chain.py` per tenant (hourly is a reasonable default).
- Require the GitHub Actions CI pipeline on `main` via branch protection.
