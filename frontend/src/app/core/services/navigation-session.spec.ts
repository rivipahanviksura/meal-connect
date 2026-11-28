
import { TestBed } from '@angular/core/testing';
import { NavigationSessionService } from './navigation-session';

describe('NavigationSessionService – MEAL-71', () => {
  let service: NavigationSessionService;

  beforeEach(() => {
    TestBed.configureTestingModule({});

    service = TestBed.inject(NavigationSessionService);
  });

  it('should create the service', () => {
    expect(service).toBeTruthy();
  });


  it('should start in anonymous state until auth integration exists', () => {
    expect(service.session().status).toBe('anonymous');
    expect(service.account()).toBeNull();
    expect(service.isAuthenticated()).toBe(false);
  });

  it('should support loading state during authentication checks', () => {
    service.setLoading();

    expect(service.session().status).toBe('loading');
    expect(service.account()).toBeNull();
    expect(service.isAuthenticated()).toBe(false);
  });

  it('should remain unauthenticated when anonymous', () => {
    service.setAnonymous();

    expect(service.session().status).toBe('anonymous');
    expect(service.account()).toBeNull();
    expect(service.isAuthenticated()).toBe(false);
  });

  it('should update the account when authenticated', () => {
    service.setAuthenticatedAccount({
      userId: 1,
      role: 'business_staff',
      isActive: true,
      organizationId: 10,
      membershipActive: true,
      verificationStatus: 'approved'
    });

    expect(service.session().status).toBe('authenticated');
    expect(service.account()?.role).toBe('business_staff');
    expect(service.isAuthenticated()).toBe(true);
  });

  it('should not treat an inactive account as authenticated', () => {
    service.setAuthenticatedAccount({
      userId: 2,
      role: 'ngo_staff',
      isActive: false
    });

    expect(service.isAuthenticated()).toBe(false);
  });

  it('should clear account data on logout', () => {
    service.setAuthenticatedAccount({
      userId: 3,
      role: 'admin',
      isActive: true
    });

    service.clear();

    expect(service.session().status).toBe('anonymous');
    expect(service.account()).toBeNull();
    expect(service.isAuthenticated()).toBe(false);
  });

  it('should hide the account when loading or error', () => {
    service.setAuthenticatedAccount({
      userId: 3,
      role: 'admin',
      isActive: true
    });

    service.setLoading();

    expect(service.account()).toBeNull();
    expect(service.isAuthenticated()).toBe(false);

    service.setError();

    expect(service.session().status).toBe('error');
    expect(service.account()).toBeNull();
    expect(service.isAuthenticated()).toBe(false);
  });
});
