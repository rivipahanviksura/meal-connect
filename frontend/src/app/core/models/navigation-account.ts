
export type AccountRole =
  | 'business_staff'
  | 'ngo_staff'
  | 'admin';

export type VerificationStatus =
  | 'draft'
  | 'pending'
  | 'approved'
  | 'rejected'
  | 'suspended';

export interface NavigationAccount {
  userId: number;
  role: AccountRole;
  isActive: boolean;

  organizationId?: number;
  membershipActive?: boolean;
  verificationStatus?: VerificationStatus;
}

export type NavigationSession =
  | { status: 'loading' }
  | { status: 'anonymous' }
  | { status: 'authenticated'; account: NavigationAccount }
  | { status: 'error' };






export type DecisionAction = 'approve' | 'reject' | 'request_corrections';
export type AdminDecisionValue = 'approved' | 'rejected' | 'request_corrections';

export interface VerificationDocument {
  document_id?: number | string;
  id?: number | string;
  original_filename?: string;
  name?: string;
  file_name?: string;
  review_status?: string;
  document_type?: string;
  type?: string;
  status?: string;
  note?: string;
  review_note?: string | null;
  url?: string;
}

export interface StatusHistoryItem {
  id?: number | string;
  status?: string;
  verification_status?: string;
  action?: string;
  decision?: string;
  reason?: string | null;
  review_note?: string | null;
  internal_comment?: string | null;
  internal_note?: string | null;
  decided_by?: string | null;
  actor?: string | null;
  changed_at?: string | null;
  reviewed_at?: string | null;
  created_at?: string | null;
}

export interface DecisionHistoryItem extends StatusHistoryItem {}

export interface ApplicationSummaryItem {
  application_id: number | string;
  id?: number | string;
  organization_id: number | string;
  name?: string;
  organization_name?: string;
  status?: VerificationStatus | string;
  verification_status?: VerificationStatus | string;
  review_note?: string | null;
  correction_note?: string | null;
  draft_details?: Record<string, unknown> | null;
}

export interface MyApplicationsResponse {
  data: ApplicationSummaryItem[];
}

export interface OrganizationApplicationDetail {
  id?: number | string;
  application_id?: number | string;
  organization_id?: number | string;
  organization_name?: string;
  name?: string;
  organization_type?: string;
  verification_status: VerificationStatus | string;
  status?: VerificationStatus | string;
  review_note?: string | null;
  reviews?: unknown[];
  status_history: StatusHistoryItem[];
  history?: StatusHistoryItem[];
  documents: VerificationDocument[];
}

export interface OrganizationApplicationDetailResponse {
  data: OrganizationApplicationDetail;
}

export interface DecisionRequestPayload {
  decision: AdminDecisionValue;
  review_note: string;
}

export interface DecisionResponsePayload {
  data?: {
    application_id?: number | string;
    verification_status?: VerificationStatus | string;
    review_note?: string | null;
    message?: string;
  };
  message?: string;
}

export interface ResubmitRequestPayload {
  correction_note?: string;
}

export interface ApiErrorBody {
  code?: string;
  message?: string;
  fields?: Record<string, string[] | string>;
}

export interface ApiErrorEnvelope {
  error?: ApiErrorBody;
  code?: string;
  message?: string;
  fields?: Record<string, string[] | string>;
}