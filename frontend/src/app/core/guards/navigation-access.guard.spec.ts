
import { TestBed } from '@angular/core/testing';
import { Router, UrlTree, provideRouter } from '@angular/router';
import type { CanActivateFn } from '@angular/router';

import { navigationAccessGuard } from './navigation-access.guard';
import { NavigationSessionService } from '../services/navigation-session';
import type { NavigationAccount } from '../models/navigation-account';

describe('Navigation Access Guard – MEAL-71', () => {
  let router: Router;
  let session: NavigationSessionService;

  const restaurant: NavigationAccount = {
    userId: 1,
    role: 'business_staff',
    isActive: true,
    organizationId: 10,
    membershipActive: true,
    verificationStatus: 'approved'
  };

  const ngo: NavigationAccount = {
    userId: 2,
    role: 'ngo_staff',
    isActive: true,
    organizationId: 20,
    membershipActive: true,
    verificationStatus: 'approved'
  };

  const admin: NavigationAccount = {
    userId: 3,
    role: 'admin',
    isActive: true
  };

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideRouter([])]
    });

    router = TestBed.inject(Router);
    session = TestBed.inject(NavigationSessionService);
  });

  function check(
    roles: Parameters<typeof navigationAccessGuard>[0]
  ): boolean | UrlTree {
    const guard: CanActivateFn = navigationAccessGuard(roles);

    return TestBed.runInInjectionContext(() =>
      guard({} as never, {} as never)
    ) as boolean | UrlTree;
  }

  function redirectPath(result: boolean | UrlTree): string | null {
    return result instanceof UrlTree
      ? router.serializeUrl(result)
      : null;
  }

  it('redirects anonymous users to Login', () => {
    session.setAnonymous();

    expect(
      redirectPath(check(['business_staff']))
    ).toBe('/login');
  });

  it('denies access while loading', () => {
    session.setLoading();

    expect(
      redirectPath(check(['business_staff']))
    ).toBe('/unauthorized');
  });

  it('denies access when session resolution fails', () => {
    session.setError();

    expect(
      redirectPath(check(['business_staff']))
    ).toBe('/unauthorized');
  });

  it('allows an approved Restaurant on Restaurant routes', () => {
    session.setAuthenticatedAccount(restaurant);

    expect(check(['business_staff'])).toBe(true);
  });

  it('blocks a Restaurant from NGO routes', () => {
    session.setAuthenticatedAccount(restaurant);

    expect(
      redirectPath(check(['ngo_staff']))
    ).toBe('/unauthorized');
  });

  it('allows an approved NGO on NGO routes', () => {
    session.setAuthenticatedAccount(ngo);

    expect(check(['ngo_staff'])).toBe(true);
  });

  it('blocks an NGO from Restaurant routes', () => {
    session.setAuthenticatedAccount(ngo);

    expect(
      redirectPath(check(['business_staff']))
    ).toBe('/unauthorized');
  });

  it('allows an active Admin without organization membership', () => {
    session.setAuthenticatedAccount(admin);

    expect(check(['admin'])).toBe(true);
  });

  it('blocks inactive Admin accounts', () => {
    session.setAuthenticatedAccount({
      ...admin,
      isActive: false
    });

    expect(
      redirectPath(check(['admin']))
    ).toBe('/unauthorized');
  });

  it.each(['draft', 'pending', 'rejected', 'suspended'] as const)(
    'blocks %s Restaurant applicants from protected routes',
    status => {
      session.setAuthenticatedAccount({
        ...restaurant,
        verificationStatus: status
      });

      expect(
        redirectPath(check(['business_staff']))
      ).toBe('/unauthorized');
    }
  );

  it('blocks inactive organization memberships', () => {
    session.setAuthenticatedAccount({
      ...restaurant,
      membershipActive: false
    });

    expect(
      redirectPath(check(['business_staff']))
    ).toBe('/unauthorized');
  });

  it('blocks accounts without an organization ID', () => {
    session.setAuthenticatedAccount({
      ...ngo,
      organizationId: undefined
    });

    expect(
      redirectPath(check(['ngo_staff']))
    ).toBe('/unauthorized');
  });

  it('blocks inactive Restaurant accounts', () => {
    session.setAuthenticatedAccount({
      ...restaurant,
      isActive: false
    });

    expect(
      redirectPath(check(['business_staff']))
    ).toBe('/unauthorized');
  });
});
