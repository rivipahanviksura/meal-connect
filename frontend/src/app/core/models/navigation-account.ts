
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

export interface VerificationDocument {
  id: number | string;
  name?: string;
  file_name?: string;
  document_type?: string;
  type?: string;
  status?: string;
  note?: string;
  review_note?: string | null;
  url?: string;
}

export interface DecisionHistoryItem {
  id: number | string;
  action: DecisionAction | string;
  reason?: string | null;
  internal_comment?: string | null;
  internal_note?: string | null;
  decided_by?: string | null;
  actor?: string | null;
  reviewed_at?: string | null;
  created_at?: string | null;
}

export interface ApplicationSummaryItem {
  application_id: number | string;
  id?: number | string;
  organization_id: number | string;
  name?: string;
  organization_name?: string;
  status: VerificationStatus | string;
  review_note?: string | null;
  correction_note?: string | null;
  draft_details?: Record<string, unknown> | null;
}

export interface MyApplicationsResponse {
  data: ApplicationSummaryItem[];
}

export interface OrganizationApplicationDetail {
  id: number | string;
  application_id?: number | string;
  organization_id?: number | string;
  organization_name?: string;
  name?: string;
  organization_type?: string;
  status: VerificationStatus | string;
  review_note?: string | null;
  documents?: VerificationDocument[];
  history?: DecisionHistoryItem[];
}

export interface OrganizationApplicationDetailResponse {
  data?: OrganizationApplicationDetail;
}

export interface DecisionRequestPayload {
  action: DecisionAction;
  reason?: string;
  internal_comment?: string;
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
