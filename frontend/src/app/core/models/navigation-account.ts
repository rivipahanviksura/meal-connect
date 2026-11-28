
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
