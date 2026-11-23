
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
  name: string;
  document_type?: string;
  status?: string;
  note?: string;
}

export interface DecisionHistoryItem {
  id: number | string;
  action: DecisionAction | string;
  reason?: string;
  internal_comment?: string;
  decided_by?: string;
  reviewed_at?: string;
  created_at?: string;
}

export interface ApplicationSummaryItem {
  application_id: number;
  organization_id: number;
  name: string;
  status: VerificationStatus | string;
  review_note?: string | null;
  draft_details?: Record<string, unknown> | null;
}

export interface MyApplicationsResponse {
  data: ApplicationSummaryItem[];
}

export interface OrganizationApplicationDetail {
  id: number | string;
  organization_id?: number;
  organization_name?: string;
  name?: string;
  organization_type?: string;
  status: VerificationStatus | string;
  review_note?: string | null;
  documents?: VerificationDocument[];
  history?: DecisionHistoryItem[];
}

export interface DecisionRequestPayload {
  action: DecisionAction;
  reason?: string;
  internal_comment?: string;
}
