
import { inject } from '@angular/core';
import {
  CanActivateFn,
  Router
} from '@angular/router';

import { NavigationSessionService } from '../services/navigation-session';
import type {
  AccountRole
} from '../models/navigation-account';

export function navigationAccessGuard(
  allowedRoles: readonly AccountRole[]
): CanActivateFn {
  return () => {
    const router = inject(Router);
    const sessionService = inject(NavigationSessionService);

    const session = sessionService.session();

    if (session.status === 'anonymous') {
      return router.createUrlTree(['/login']);
    }

    if (session.status !== 'authenticated') {
      return router.createUrlTree(['/unauthorized']);
    }

    const account = session.account;

    if (!account.isActive) {
      return router.createUrlTree(['/unauthorized']);
    }

    if (!allowedRoles.includes(account.role)) {
      return router.createUrlTree(['/unauthorized']);
    }

    // Admin accounts do not require organization membership.
    if (account.role === 'admin') {
      return true;
    }

    // Restaurant and NGO protected pages require an approved
    // organization and an active membership.
    if (
      account.organizationId == null ||
      account.membershipActive !== true ||
      account.verificationStatus !== 'approved'
    ) {
      return router.createUrlTree(['/unauthorized']);
    }

    return true;
  };
}
