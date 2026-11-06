# Meal Connect MVP — Database ER Diagram

**Jira:** MEAL-213
**Schema revision:** `66af9d4181e5` (parent: `d99d12936307`)
**Database:** PostgreSQL
**Application tables:** 11 (`alembic_version` is separate)

## Entity relationships

```mermaid
erDiagram
    USERS ||--o{ ORGANIZATION_MEMBERSHIPS : linked_to
    ORGANIZATIONS ||--o| ORGANIZATION_MEMBERSHIPS : has_account
    ORGANIZATIONS ||--o{ ORGANIZATION_DOCUMENTS : has_documents
    ORGANIZATIONS ||--o{ ORGANIZATION_VERIFICATIONS : has_reviews
    ORGANIZATIONS ||--o{ DONATIONS : publishes
    DONATIONS ||--o{ DONATION_REQUESTS : receives
    ORGANIZATIONS ||--o{ DONATION_REQUESTS : makes_as_ngo
    DONATION_REQUESTS ||--o| PICKUPS : creates
    PICKUPS ||--o| DISTRIBUTION_RECORDS : has_distribution
    USERS ||--o{ NOTIFICATIONS : receives
    USERS ||--o{ STATUS_HISTORY : performs_changes

    USERS {
        bigint user_id PK
        varchar email UK
        varchar password_hash
        enum role
        enum account_status
    }

    ORGANIZATIONS {
        bigint organization_id PK
        enum type
        varchar registration_number UK
        enum verification_status
        varchar registration_authority
        date registration_date
        date registration_expiry_date
        varchar representative_name
        varchar representative_designation
        varchar pickup_location
        jsonb operational_details
        timestamptz submitted_at
        bigint verified_by_user_id FK
    }

    ORGANIZATION_MEMBERSHIPS {
        bigint membership_id PK
        bigint organization_id FK,UK
        bigint user_id FK
        enum membership_role
        enum member_status
    }

    ORGANIZATION_DOCUMENTS {
        bigint document_id PK
        bigint organization_id FK
        bigint uploaded_by_user_id FK
        varchar document_type
        varchar storage_key UK
        varchar original_filename
        varchar content_type
        bigint file_size_bytes
        varchar review_status
        timestamptz uploaded_at
        timestamptz reviewed_at
    }

    ORGANIZATION_VERIFICATIONS {
        bigint verification_id PK
        bigint organization_id FK
        bigint reviewed_by_user_id FK
        enum decision
        text review_note
        timestamptz reviewed_at
    }

    DONATIONS {
        bigint donation_id PK
        bigint organization_id FK
        bigint created_by_user_id FK
        numeric total_quantity
        numeric allocated_quantity
        enum status
    }

    DONATION_REQUESTS {
        bigint request_id PK
        bigint donation_id FK
        bigint ngo_organization_id FK
        bigint requested_by_user_id FK
        numeric requested_quantity
        bigint reviewed_by_user_id FK
        enum status
    }

    PICKUPS {
        bigint pickup_id PK
        bigint request_id FK,UK
        bigint collector_user_id FK
        varchar pin_verifier
        timestamptz pin_expires_at
        int pin_failed_attempts
        timestamptz pin_locked_until
        timestamptz pin_verified_at
        int pin_generation
        bigint handover_confirmed_by_user_id FK
        timestamptz handover_confirmed_at
        enum status
    }

    DISTRIBUTION_RECORDS {
        bigint distribution_id PK
        bigint pickup_id FK,UK
        bigint recorded_by_user_id FK
        numeric distributed_quantity
        int beneficiary_count
        timestamptz distributed_at
    }

    NOTIFICATIONS {
        bigint notification_id PK
        bigint recipient_user_id FK
        varchar notification_type
        boolean is_read
    }

    STATUS_HISTORY {
        bigint status_history_id PK
        varchar entity_type
        bigint entity_id
        bigint changed_by_user_id FK
        varchar new_status
    }
```

## Cardinality and integrity rules

- **One authorized account per organization:** `organization_memberships.organization_id` has the unique constraint `uq_membership_single_account_per_org`. An organization can have **at most one** membership record. Organization signup must create the organization and its membership atomically.
- **Multiple organizations per user:** the current schema does *not* prohibit a user from being linked to several organizations. Application-level account policy must be enforced separately if this is undesired.
- **Verification:** documents and Admin review history are separate. `organizations.verification_status` controls approval; `submitted_at` distinguishes an unsubmitted draft from a submitted application within the agreed workflow.
- **Donation request:** a donation can have several NGO requests. Each request has one requested quantity; approval or rejection of that full quantity is enforced by backend service logic.
- **Allocation:** `donations.allocated_quantity` is constrained to `0 <= allocated_quantity <= total_quantity`. Concurrent approval must use a safe transaction/locking strategy.
- **Pickup:** `pickups.request_id` is unique, so a donation request can have at most one pickup. The PIN verifier, expiry, attempt limit, lock state and confirmation timestamps support the approved workflow but do not implement it by themselves.
- **Handover vs distribution:** PIN verification is separate from Restaurant handover confirmation (`handover_confirmed_at`, pickup status `picked_up`). NGO distribution is subsequently recorded in `distribution_records`; `distribution_records.pickup_id` is unique.
- **Legacy field:** `pickups.collector_user_id` still exists in this migration for compatibility, but the MVP pickup representative does not have a platform login. The field must not be used by the new workflow.
- **Status history:** `status_history.entity_type` + `entity_id` is a generic reference, **not** a database-enforced foreign key to each business table.
- **Private documents:** `organization_documents.storage_key` is unique and references private storage. The documents are not stored as database blobs; file access must be authorized by backend APIs.

## Additional foreign keys not drawn as diagram lines

The diagram emphasizes the main business flow. These columns also refer to `users.user_id`: `organizations.verified_by_user_id`, `organization_documents.uploaded_by_user_id`, `organization_verifications.reviewed_by_user_id`, `donations.created_by_user_id`, `donation_requests.requested_by_user_id`, `donation_requests.reviewed_by_user_id`, `pickups.collector_user_id` (legacy), `pickups.handover_confirmed_by_user_id`, and `distribution_records.recorded_by_user_id`. The primary workflow relationships and these auxiliary foreign keys together describe the implementation.

## Scope and implementation note

This is a **selected-column physical ER overview**, not a full inventory of every database column. It documents the migrated schema, not proof that registration, verification, PIN generation, authorization, or food-distribution services are already implemented. The `alembic_version` table is managed by Alembic and is not one of the 11 application tables.
