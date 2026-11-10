<!--
Sync Impact Report
Version change: 1.1.0 -> 1.2.0
Modified principles: none
Added principles: VI. Domain-Driven Design and Ubiquitous Language
Added sections: none
Expanded sections: Development Workflow (domain glossary and consistent terminology)
Removed sections: none
Follow-up TODOs: Confirm the original ratification date.
-->

# MISP IOC Scoring Constitution

## Core Principles

### I. Evidence-Based, Explainable Scoring
Every score MUST be traceable to documented scoring criteria and the input data that
triggered those criteria. Changes to scoring behavior MUST document the rationale and
expected impact so that operators can understand and reproduce a result.

### II. Preserve Indicator and Source Data
Scoring MUST NOT silently alter the meaning or contents of source indicators or their
associated MISP data. Normalization MUST be explicit, consistent, and covered by tests;
when source data cannot be interpreted safely, the software MUST report the problem
instead of fabricating a value.

### III. Deterministic, Tested Behavior
Given the same valid inputs, configuration, and software version, scoring MUST produce
the same result. Changes to scoring rules, parsing, or data handling MUST include
automated tests for expected behavior and relevant boundary cases. Defects MUST receive
regression coverage when practical.

### IV. Treat Threat Data as Untrusted
Indicators, feeds, and imported event content MUST be treated as untrusted input.
Parsing and output handling MUST prevent indicator content from being interpreted as
commands, executable markup, or trusted configuration. Secrets and sensitive data MUST
not be exposed in logs or outputs.

### V. Prefer Small, Interoperable Changes
Implementations MUST favor the simplest design that meets the documented need and MUST
preserve established project and MISP data conventions. New dependencies, formats, and
interfaces MUST have a documented need; compatibility-affecting changes MUST be
identified and documented before release.

### VI. Domain-Driven Design and Ubiquitous Language
The project MUST maintain a shared, documented domain vocabulary for concepts such as
IOC, source observation, scoring candidate, and score. Names used in requirements,
documentation, code, and operator-facing messages MUST use these terms consistently;
when a term's meaning changes, the glossary and affected materials MUST be updated.
Domain rules MUST be modeled separately from infrastructure and external MISP
integration concerns, using Domain-Driven Design patterns where they clarify domain
boundaries or behavior. The project MUST NOT introduce patterns or abstractions without
a demonstrated domain need. This keeps analyst and implementation understanding aligned
while avoiding unnecessary complexity.

## Architecture, Data, and Security Requirements

The application MUST use Python and Docker, with three application services: a database
container; a collector/normalizer container that retrieves data from MISP and normalizes
it; and a scoring/sharing container that calculates scores and publishes IOCs to other
MISP sync peers. The data-manipulation library MUST be selected based on the actual
normalization and scoring needs rather than added without justification.

The database MUST persist structured source and normalized data needed by the Carioca
scoring algorithm, including enough provenance to explain which input values contributed
to a score. The relational database engine MUST be selected between SQLite and
PostgreSQL based on deployment and operational requirements before implementation is
finalized. Scoring and sharing MUST preserve MISP data conventions and make score
results traceable to their inputs and documented criteria.

Input validation MUST occur at data boundaries, including imported or externally
provided indicator values. Errors MUST be explicit and actionable without echoing
sensitive values unnecessarily. Dependencies MUST be selected and updated with regard
to security and maintenance. Any change that affects handling of indicator data,
credentials, or external inputs MUST be reviewed for security and privacy implications.

## Development Workflow

Changes MUST include tests appropriate to the affected behavior, and changes to scoring
criteria MUST include documentation of the criteria and rationale. Before a change is
merged, its applicable automated tests and project-defined quality checks MUST pass.
Reviewers MUST verify that changes follow this constitution and that compatibility or
security consequences are documented. Changes to domain concepts MUST use the shared
vocabulary and update the domain glossary when needed. If a check cannot be run, the
limitation and its impact MUST be stated in the change description.

## Governance

This constitution governs project development practices. Amendments MUST be proposed
with their rationale, reviewed and approved by the project maintainer, and reflected in
the version and amendment date below. A change to this constitution MUST include a
review of affected project guidance and active work for consistency; related artifacts
MUST be updated when needed.

Constitution versions use semantic versioning: MAJOR for backward-incompatible
governance changes or removal/redefinition of a principle; MINOR for new principles,
sections, or materially expanded requirements; PATCH for clarifications and
non-semantic wording changes. Changes MUST increment the appropriate version component.

Every change review MUST assess compliance with the principles and applicable
requirements above. Exceptions MUST be explicitly justified, approved by the project
maintainer, and recorded with the affected change. The project maintainer is responsible
for periodic review and for resolving identified compliance gaps.

**Version**: 1.2.0 | **Ratified**: TODO(RATIFICATION_DATE): original date unknown | **Last Amended**: 2026-11-09
