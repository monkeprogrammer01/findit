# ADR-001: Authenticate every user through University SSO

- **Status:** Accepted
- **Date:** 18 October 2026

## Context

University IT needs FindIt to use campus single sign-on. FR-05 checks the
claimant's student identity at handover. Constraint C-02 requires student IDs,
contact details, and claim answers to be encrypted at rest with AES-256 and sent
only over TLS 1.3. The security scenario requires every call to be checked with a
JWT: an unauthorised request gets HTTP 403, the attempt is written to the audit
log, and private claim answers are not returned. A second store of campus
passwords would copy identity data the university already keeps.

## Decision

FindIt stores no passwords. The application accepts only tokens issued by
University SSO. The relational database keeps a role and a stable campus
identifier for each user, which is what handover and the audit log need. Claim
answers stay behind an authorisation check in the application: a student token
cannot read them, and a desk-admin token can. A rejected call returns HTTP 403 and
is appended to the audit log.

## Alternatives considered

- Local email and password accounts, stored in the FindIt database.
- Public social login, with no check that the person is a current campus member.

## Consequences

### Positive

- Login and in-person handover use the same campus identity, which is what FR-05
  needs.
- There is no password table to breach. Contact data and claim answers stay inside
  FindIt, encrypted at rest, and leave only over TLS.
- The JWT check, the 403 response, and the audit entry are one path in the
  application container.

### Negative

- If University SSO is down, new logins fail even when the FindIt containers are
  healthy. Sessions that were already issued keep working until they expire.
  FindIt does not add a backup password, because that would recreate the
  local-account alternative.
- FindIt depends on the university identity service. Role names inside FindIt must
  be mapped from SSO identities and reviewed when campus directory groups change.
