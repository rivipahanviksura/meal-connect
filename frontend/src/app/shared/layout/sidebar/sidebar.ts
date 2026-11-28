
import { Component, computed, input } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';

import type {
  NavigationAccount
} from '../../../core/models/navigation-account';

interface NavigationItem {
  label: string;
  path: string;
}

const RESTAURANT_NAV: NavigationItem[] = [
  { label: 'Restaurant Dashboard', path: '/restaurant/dashboard' },
  { label: 'My Donations', path: '/restaurant/donations' },
  { label: 'Create Donation', path: '/restaurant/donations/create' },
  { label: 'Donation Requests', path: '/restaurant/requests' },
  { label: 'Pickup Verification / Handover', path: '/restaurant/pickups' },
  { label: 'Organization Profile', path: '/organization/profile' }
];

const NGO_NAV: NavigationItem[] = [
  { label: 'NGO Dashboard', path: '/ngo/dashboard' },
  { label: 'Browse Donations', path: '/ngo/donations' },
  { label: 'My Donation Requests', path: '/ngo/requests' },
  { label: 'Approved Requests / Pickup PINs', path: '/ngo/pickups' },
  { label: 'Distribution Records', path: '/ngo/distributions' },
  { label: 'Organization Profile', path: '/organization/profile' }
];

const ADMIN_NAV: NavigationItem[] = [
  { label: 'Admin Dashboard', path: '/admin/dashboard' },
  { label: 'Pending Organization Applications', path: '/admin/applications' },
  { label: 'Verification Document Review', path: '/admin/documents' },
  { label: 'Approve / Reject Organizations', path: '/admin/verifications' },
  { label: 'Verification History', path: '/admin/history' }
];

const APPLICANT_NAV: NavigationItem[] = [
  { label: 'Organization Profile', path: '/organization/profile' },
  { label: 'Verification Status', path: '/organization/verification' }
];

const EDITABLE_APPLICANT_NAV: NavigationItem[] = [
  ...APPLICANT_NAV,
  { label: 'Documents / Resubmission', path: '/organization/documents' }
];

@Component({
  selector: 'app-sidebar',
  imports: [RouterLink, RouterLinkActive],
  templateUrl: './sidebar.html',
  styleUrl: './sidebar.scss'
})
export class Sidebar {
  readonly account = input<NavigationAccount | null>(null);

  readonly items = computed<NavigationItem[]>(() => {
    const account = this.account();

    if (!account || !account.isActive) {
      return [];
    }

    if (account.role === 'admin') {
      return ADMIN_NAV;
    }

    if (
      account.role !== 'business_staff' &&
      account.role !== 'ngo_staff'
    ) {
      return [];
    }

    // Do not show protected links until the organization is
    // approved and its membership is active.
    if (
      account.verificationStatus === 'approved' &&
      account.membershipActive === true &&
      account.organizationId != null
    ) {
      return account.role === 'business_staff'
        ? RESTAURANT_NAV
        : NGO_NAV;
    }

    // Pending/rejected/draft applicants can use only
    // the permitted account and verification navigation.
    if (
      account.verificationStatus === 'draft' ||
      account.verificationStatus === 'rejected'
    ) {
      return EDITABLE_APPLICANT_NAV;
    }

    if (account.verificationStatus === 'pending') {
      return APPLICANT_NAV;
    }

    // Suspended or incomplete verification data: no protected
    // operations, and no editable application links.
    return [];
  });

  readonly visible = computed(() => this.items().length > 0);
}
