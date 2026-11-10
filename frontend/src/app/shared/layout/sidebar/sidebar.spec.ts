
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { Sidebar } from './sidebar';
import type { NavigationAccount } from '../../../core/models/navigation-account';

describe('Sidebar – MEAL-71', () => {
  let fixture: ComponentFixture<Sidebar>;

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

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Sidebar],
      providers: [provideRouter([])]
    }).compileComponents();

    fixture = TestBed.createComponent(Sidebar);
  });

  function setAccount(account: NavigationAccount | null): HTMLElement {
    fixture.componentRef.setInput('account', account);
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  function navText(element: HTMLElement): string {
    return element.querySelector('nav')?.textContent ?? '';
  }

  it('creates the component', () => {
    expect(fixture.componentInstance).toBeTruthy();
  });

  it('hides the sidebar for anonymous users', () => {
    const element = setAccount(null);
    expect(element.querySelector('aside')).toBeNull();
  });

  it('hides navigation for inactive accounts', () => {
    const element = setAccount({
      ...restaurant,
      isActive: false
    });

    expect(element.querySelector('aside')).toBeNull();
  });

  it('shows verified Restaurant navigation', () => {
    const text = navText(setAccount(restaurant));

    expect(text).toContain('Restaurant Dashboard');
    expect(text).toContain('Create Donation');
    expect(text).toContain('Pickup Verification / Handover');
    expect(text).not.toContain('NGO Dashboard');
    expect(text).not.toContain('Admin Dashboard');
  });

  it('shows verified NGO navigation', () => {
    const text = navText(setAccount(ngo));

    expect(text).toContain('NGO Dashboard');
    expect(text).toContain('Browse Donations');
    expect(text).toContain('Approved Requests / Pickup PINs');
    expect(text).toContain('Distribution Records');
    expect(text).not.toContain('Create Donation');
    expect(text).not.toContain('Admin Dashboard');
  });

  it('shows Admin navigation without an organization membership', () => {
    const text = navText(setAccount({
      userId: 3,
      role: 'admin',
      isActive: true
    }));

    expect(text).toContain('Admin Dashboard');
    expect(text).toContain('Pending Organization Applications');
    expect(text).toContain('Verification Document Review');
    expect(text).not.toContain('Create Donation');
  });

  it('does not grant Admin navigation to inactive admins', () => {
    const element = setAccount({
      userId: 3,
      role: 'admin',
      isActive: false
    });

    expect(element.querySelector('aside')).toBeNull();
  });

  it.each(['draft', 'rejected'] as const)(
    'shows editable applicant navigation for %s',
    status => {
      const text = navText(setAccount({
        ...restaurant,
        membershipActive: false,
        verificationStatus: status
      }));

      expect(text).toContain('Organization Profile');
      expect(text).toContain('Verification Status');
      expect(text).toContain('Documents / Resubmission');
      expect(text).not.toContain('Create Donation');
    }
  );

  it('shows restricted navigation for pending applicants', () => {
    const text = navText(setAccount({
      ...ngo,
      membershipActive: false,
      verificationStatus: 'pending'
    }));

    expect(text).toContain('Organization Profile');
    expect(text).toContain('Verification Status');
    expect(text).not.toContain('Browse Donations');
    expect(text).not.toContain('Documents / Resubmission');
  });

  it('hides navigation for suspended organizations', () => {
    const element = setAccount({
      ...restaurant,
      verificationStatus: 'suspended'
    });

    expect(element.querySelector('aside')).toBeNull();
  });

  it('does not show protected links without active membership', () => {
    const text = navText(setAccount({
      ...restaurant,
      membershipActive: false
    }));

    expect(text).not.toContain('Create Donation');
    expect(text).not.toContain('Pickup Verification / Handover');
  });

  it('does not show protected links without an organization ID', () => {
    const text = navText(setAccount({
      ...ngo,
      organizationId: undefined
    }));

    expect(text).not.toContain('Browse Donations');
    expect(text).not.toContain('Distribution Records');
  });

  it('fails closed when verification status is missing', () => {
    const element = setAccount({
      ...restaurant,
      verificationStatus: undefined
    });

    expect(element.querySelector('aside')).toBeNull();
  });

  it('updates navigation when verification becomes approved', () => {
    let text = navText(setAccount({
      ...ngo,
      verificationStatus: 'pending'
    }));

    expect(text).not.toContain('Browse Donations');

    text = navText(setAccount(ngo));

    expect(text).toContain('Browse Donations');
  });

  it('removes protected navigation after membership is deactivated', () => {
    let text = navText(setAccount(restaurant));
    expect(text).toContain('Create Donation');

    text = navText(setAccount({
      ...restaurant,
      membershipActive: false
    }));

    expect(text).not.toContain('Create Donation');
  });

  it('renders accessible navigation links', () => {
    const element = setAccount(restaurant);

    expect(
      element.querySelector('nav[aria-label="Account navigation"]')
    ).not.toBeNull();

    const links = element.querySelectorAll<HTMLAnchorElement>('nav a');

    expect(links.length).toBeGreaterThan(0);

    links.forEach(link => {
      expect(link.getAttribute('href')).toBeTruthy();
    });
  });
});
