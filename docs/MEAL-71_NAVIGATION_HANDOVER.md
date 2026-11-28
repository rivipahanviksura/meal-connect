
# MEAL-71 – Shared Navigation & Layout Handover

## Implemented

- Responsive shared application layout
- Header, sidebar and footer components
- Public Home, Login and Register navigation
- Role-based navigation for Restaurant, NGO and Admin
- Restricted navigation for pending/rejected applicants
- Active-route indicators
- Loading, error and unauthorized UI
- NavigationSessionService
- Navigation access guard foundation
- Logout button interface (disabled until auth integration)
- Component and guard unit tests

## Authentication Integration Dependency

The authentication feature owner must integrate backend-confirmed
account information with NavigationSessionService.

Account roles and organization verification states must come from
the trusted backend, not from user-selected frontend values.

The actual logout implementation must:

1. Complete the required authentication logout process.
2. Clear locally held authentication credentials.
3. Reset NavigationSessionService.
4. Redirect the user appropriately.

The Logout control must remain disabled until this integration exists.

## Protected Feature Routes

Restaurant, NGO and Admin feature pages are owned by their
respective feature developers.

When those routes are registered, the appropriate navigation
access guards must be applied and tested.

Navigation guards improve frontend UX but do not replace
backend authentication, ownership checks or RBAC enforcement.

## Registration Rules

Public registration is available only for:

- Restaurant / Food Business
- NGO / Charity

Volunteer and Admin accounts must not be publicly registered.

## Remaining Integration Checks

- Authentication session restoration
- Navigation updates after account/verification status changes
- Real logout behavior
- Protected route registration and navigation
- Pending/rejected applicant access to permitted pages
- End-to-end permission and accessibility checks

## Verification

- Angular production build: Passed
- Unit tests: Run successfully during MEAL-71 development
- Final authentication and protected-route integration: Pending
