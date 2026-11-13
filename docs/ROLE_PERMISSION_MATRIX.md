# Meal Connect MVP – Role Permission Matrix

**Jira Issue:** MEAL-80
**Status:** Approved design specification for backend implementation
**Applicable Decisions:** DEC-01 through DEC-07
**Database Revision:** `66af9d4181e5`

## 1. Account Roles

The MVP supports three authenticated account roles:

- **Restaurant/Business:** `business_staff`
- **NGO/Charity:** `ngo_staff`
- **System Admin:** `admin`

Public registration is restricted to Restaurant/Business and NGO/Charity organizations.

Admin accounts are provisioned internally.

Each Restaurant/NGO organization has exactly one authorized login account.

Volunteers and pickup representatives do not register or log in to the platform. The legacy `volunteer` enum value must not grant permissions.

### Implementation Clarification – MEAL-213 Alignment

The approved MEAL-213 database migration provides the organization membership constraint and verification document metadata required by the MVP.

For new public registrations:

- The backend must never accept a client-selected privileged role.
- The legacy `volunteer` role must not be used to create independently registered Volunteer accounts.
- Any historical placeholder-role approach described in API_ENDPOINTS.md requires explicit reconciliation with the approved onboarding implementation before development.
- Restaurant/NGO account roles do not independently grant organization permissions.
- Privileged access requires an active account, active membership, approved organization, and resource ownership checks.
- The database enforces at most one membership per organization.
- The additional one-organization-per-applicant-account requirement must be enforced by the registration/application service, with concurrency-safe validation.
- The public API organization type values must be mapped explicitly to the supported database organization types.
- Organization document metadata and pickup PIN persistence fields are implemented in database revision `66af9d4181e5`; their API services are still planned.

The legacy organization creation and verification routes must not bypass the approved registration and Admin verification workflow.

Any changes to canonical API request fields, endpoint paths, or onboarding behavior must be synchronized with API_ENDPOINTS.md and the MEAL-62 contract before implementation.

## 2. Role Permission Matrix

| Operation | Restaurant | NGO | Admin |
|---|---|---|---|
| Public registration | Allow | Allow | Deny |
| Login and own account | Allow | Allow | Allow |
| View own verification status | Allow | Allow | N/A |
| Manage own permitted registration details | Allow | Allow | N/A |
| Upload own verification documents | Allow | Allow | Deny |
| Review organization applications | Deny | Deny | Allow |
| Approve/reject organization | Deny | Deny | Allow |
| Create and manage own donations | Allow after approval | Deny | Deny |
| Browse available donations | Deny | Allow after approval | Deny |
| Submit donation requests | Deny | Allow after approval | Deny |
| Approve/reject donation requests | Allow for owned donations | Deny | Deny |
| Receive/regenerate pickup PIN | Deny | Allow for own approved requests | Deny |
| Verify pickup PIN | Allow for owned donation requests | Deny | Deny |
| Confirm restaurant handover | Allow for owned pickups | Deny | Deny |
| Record food distribution | Deny | Allow for own completed pickups | Deny |

## 3. Authorization Requirements

Protected operations must enforce:

1. Valid authentication.
2. Active user account.
3. Required user role.
4. Active organization membership.
5. Approved organization verification.
6. Correct organization and resource ownership.
7. Valid operation-specific status transitions.

Admin operations require an authenticated, active Admin account and explicit Admin permission. An organization membership is not required for Admin.

Client-provided role, organization ID, or user ID must never be trusted as authorization evidence.

## 4. Pending and Rejected Organizations

Pending and rejected Restaurant/NGO accounts may log in if their user account is active.

They may view their own application status and complete permitted corrections or document resubmission.

They must not create donations, request donations, approve requests, verify pickup PINs, confirm handovers, or record distributions until approved.

Organization verification status and user account status are separate concepts.

## 5. Organization Ownership

Each organization may have only one authorized account membership.

The database constraint `uq_membership_single_account_per_org` enforces this rule.

A user may access only resources belonging to their authorized organization.

Restaurant actions must be restricted to their own donations and associated pickup requests.

NGO actions must be restricted to their own donation requests, PIN issuance, and distribution records.

## 6. Pickup PIN Security

- A pickup PIN is a cryptographically generated six-digit one-time secret.
- Only the authorized NGO may receive a newly issued PIN.
- Plaintext PINs must not be stored in database records, notification messages, or logs.
- PIN verification is restricted to the Restaurant associated with the approved donation request.
- Verification must check expiry, ownership, attempt limits, and single-use conditions.
- PIN regeneration must invalidate the previously issued PIN.
- Successful PIN verification does not mark a pickup as completed.
- The Restaurant must explicitly confirm handover.
- Distribution completion is a separate subsequent NGO action.

Pickup representatives receive the PIN from their NGO outside the authenticated application and present it during pickup.

## 7. Backend Enforcement

Authorization must be enforced through backend dependencies and service-layer resource checks.

Frontend role-based visibility is only a user-interface convenience and is not a security control.

Return the approved standardized API error format for authentication, authorization, validation, and resource-state errors.

## 8. Related Implementation Tasks

- **MEAL-10:** Secure registration and login
- **MEAL-11:** Role-based access control implementation
- **MEAL-76:** Registration and login frontend
- **MEAL-77:** Authentication endpoints
- **MEAL-78:** User persistence
- **MEAL-80:** Role permission specification
- **MEAL-81:** Backend authorization dependencies
- **MEAL-83:** Role and ownership boundary testing
- **MEAL-213:** Database schema alignment

## 9. Acceptance Criteria

- [x] Restaurant, NGO, and Admin roles documented.
- [x] Public registration restrictions documented.
- [x] One-account-per-organization policy documented.
- [x] Volunteer login exclusion documented.
- [x] Pending/rejected organization restrictions documented.
- [x] Organization ownership checks documented.
- [x] Pickup PIN authorization documented.
- [x] Separate pickup and distribution events documented.
- [ ] Final documentation reviewed and merged into `develop`.