# ADR-002: Model the claim lifecycle with the State pattern

- **Status:** Accepted
- **Date:** 8 November 2026

## Context

A claim on a found item moves through `pending → approved → returned`, or
`pending → rejected` (FR-04, FR-05). Each action is allowed only in some states and
changes more than the claim itself:

| Action | pending | approved | rejected | returned |
| --- | --- | --- | --- | --- |
| approve | yes: item becomes `claimed`, other pending claims are rejected | no | no | no |
| reject | yes | no | no | no |
| hand over | no | yes: claim and item become `returned` | no | no |

The rules are used by three endpoints (approve, reject, handover) and by the
automatic rejection of competing claims. A mistake here is serious: handing an
item over twice, or approving a second owner, cannot be undone at the desk.

## Decision

Use the **State** pattern in `backend/app/domain/claim_states.py`.

- `ClaimState` is the abstract state. By default `approve()`, `reject()` and
  `hand_over()` raise `InvalidTransition`.
- `PendingState`, `ApprovedState`, `RejectedState` and `ReturnedState` override
  only the actions they allow and return a `Transition` (new claim status, new item
  status, whether to reject other pending claims).
- `state_for(status)` picks the state object for the status stored in the
  database.
- `application/claims.py` applies the `Transition` to the ORM objects and maps
  `InvalidTransition` to HTTP 409.

The domain module does not import SQLAlchemy or FastAPI, so the rules are tested
without a database (`tests/test_claims.py::test_state_rules`).

## Alternatives considered

- **`if`/`elif` on `claim.status` in each endpoint.** Simpler at first, but the
  same status checks would be repeated in approve, reject, handover and the
  automatic rejection. A missing branch would silently allow an illegal action,
  such as a second handover.
- **A generic state-machine library.** It handles "which status comes next", but
  our transitions carry side effects (reserve the item, reject competitors). Those
  rules would live in callbacks outside the domain layer.

## Consequences

**Positive**

- Every lifecycle rule is in one class, and actions are refused by default.
- A new state (for example `cancelled` by the student) is one new class.
- The rules are unit-tested without a database or HTTP.

**Negative**

- Four small classes for a lifecycle that fits in one table.
- The application layer has to translate `Transition` into ORM updates, which is
  one more step to read when debugging.
