import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HttpErrorResponse } from '@angular/common/http';
import { ActivatedRoute, convertToParamMap, Router } from '@angular/router';
import { of, Subject, throwError } from 'rxjs';
import { signal } from '@angular/core';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { OrganizationDecision } from './organization-decision';
import { OrganizationVerificationService } from '../../core/services/organization-verification.service';
import {
  NavigationSession,
  OrganizationApplicationDetail,
} from '../../core/models/navigation-account';
import { navigationAccessGuard } from '../../core/guards/navigation-access.guard';
import { NavigationSessionService } from '../../core/services/navigation-session';

describe('OrganizationDecision', () => {
  let fixture: ComponentFixture<OrganizationDecision>;
  let verificationServiceMock: {
    getApplicationById: ReturnType<typeof vi.fn>;
    submitDecision: ReturnType<typeof vi.fn>;
    getMyApplications: ReturnType<typeof vi.fn>;
    resubmitApplication: ReturnType<typeof vi.fn>;
  };

  const mockApplication: OrganizationApplicationDetail = {
    id: 101,
    organization_id: 12,
    organization_name: 'Hope Kitchen',
    organization_type: 'NGO',
    status: 'pending',
    documents: [
      { id: 1, name: 'registration.pdf', status: 'submitted' },
    ],
    history: [],
  };

  beforeEach(async () => {
    verificationServiceMock = {
      getApplicationById: vi.fn().mockReturnValue(of(mockApplication)),
      submitDecision: vi.fn(),
      getMyApplications: vi.fn(),
      resubmitApplication: vi.fn(),
    };

    await TestBed.configureTestingModule({
      imports: [OrganizationDecision],
      providers: [
        { provide: OrganizationVerificationService, useValue: verificationServiceMock },
        {
          provide: ActivatedRoute,
          useValue: {
            snapshot: {
              paramMap: convertToParamMap({ id: '101' }),
            },
          },
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(OrganizationDecision);
    fixture.detectChanges();
  });

  it('approves an organization application after confirmation', () => {
    verificationServiceMock.submitDecision.mockReturnValue(
      of({ ...mockApplication, status: 'approved' })
    );

    const host = fixture.nativeElement as HTMLElement;
    const buttons = Array.from(host.querySelectorAll('button'));
    const approveBtn = buttons.find((b) => b.textContent?.trim() === 'Approve');
    approveBtn?.click();
    fixture.detectChanges();

    const reviewBtn = Array.from(host.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Review & Confirm')
    );
    reviewBtn?.click();
    fixture.detectChanges();

    const confirmBtn = Array.from(host.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Confirm Decision')
    );
    confirmBtn?.click();
    fixture.detectChanges();

    expect(verificationServiceMock.submitDecision).toHaveBeenCalledWith('101', {
      action: 'approve',
      reason: undefined,
      internal_comment: undefined,
    });
    expect(host.textContent).toContain('Decision "approve" submitted successfully.');
  });

  it('requires a meaningful reason and submits rejection with reason and internal note', () => {
    verificationServiceMock.submitDecision.mockReturnValue(
      of({ ...mockApplication, status: 'rejected' })
    );

    const host = fixture.nativeElement as HTMLElement;
    const rejectBtn = Array.from(host.querySelectorAll('button')).find(
      (b) => b.textContent?.trim() === 'Reject'
    );
    rejectBtn?.click();
    fixture.detectChanges();

    const reviewBtn = Array.from(host.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Review & Confirm')
    );
    reviewBtn?.click();
    fixture.detectChanges();

    expect(host.textContent).toContain('Please enter a meaningful reason');

    const textarea = host.querySelector('#decision-reason') as HTMLTextAreaElement;
    textarea.value = 'Incomplete registration certificate';
    textarea.dispatchEvent(new Event('input'));

    const noteInput = host.querySelector('#internal-comment') as HTMLInputElement;
    noteInput.value = 'Checked registry database';
    noteInput.dispatchEvent(new Event('input'));
    fixture.detectChanges();

    reviewBtn?.click();
    fixture.detectChanges();

    const confirmBtn = Array.from(host.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Confirm Decision')
    );
    confirmBtn?.click();
    fixture.detectChanges();

    expect(verificationServiceMock.submitDecision).toHaveBeenCalledWith('101', {
      action: 'reject',
      reason: 'Incomplete registration certificate',
      internal_comment: 'Checked registry database',
    });
  });

  it('submits a correction request with feedback', () => {
    verificationServiceMock.submitDecision.mockReturnValue(
      of({ ...mockApplication, status: 'corrections_requested' })
    );

    const host = fixture.nativeElement as HTMLElement;
    const correctionBtn = Array.from(host.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Request Corrections')
    );
    correctionBtn?.click();
    fixture.detectChanges();

    const textarea = host.querySelector('#decision-reason') as HTMLTextAreaElement;
    textarea.value = 'Please upload a clearer tax document';
    textarea.dispatchEvent(new Event('input'));
    fixture.detectChanges();

    const reviewBtn = Array.from(host.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Review & Confirm')
    );
    reviewBtn?.click();
    fixture.detectChanges();

    const confirmBtn = Array.from(host.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Confirm Decision')
    );
    confirmBtn?.click();
    fixture.detectChanges();

    expect(verificationServiceMock.submitDecision).toHaveBeenCalledWith('101', {
      action: 'request_corrections',
      reason: 'Please upload a clearer tax document',
      internal_comment: undefined,
    });
  });

  it('resets confirmation if action or reason changes before final submission', () => {
    const host = fixture.nativeElement as HTMLElement;
    const reviewBtn = Array.from(host.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Review & Confirm')
    );
    reviewBtn?.click();
    fixture.detectChanges();

    expect(host.querySelector('[aria-label="Confirm decision"]')).not.toBeNull();

    const textarea = host.querySelector('#decision-reason') as HTMLTextAreaElement;
    textarea.value = 'Updated note';
    textarea.dispatchEvent(new Event('input'));
    fixture.detectChanges();

    expect(host.querySelector('[aria-label="Confirm decision"]')).toBeNull();
  });

  it('prevents duplicate submissions while a request is in flight', () => {
    const pending$ = new Subject<OrganizationApplicationDetail>();
    verificationServiceMock.submitDecision.mockReturnValue(pending$.asObservable());

    const host = fixture.nativeElement as HTMLElement;
    const reviewBtn = Array.from(host.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Review & Confirm')
    );
    reviewBtn?.click();
    fixture.detectChanges();

    const confirmBtn = Array.from(host.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Confirm Decision')
    );
    confirmBtn?.click();
    fixture.detectChanges();

    confirmBtn?.click();
    fixture.detectChanges();

    expect(verificationServiceMock.submitDecision).toHaveBeenCalledTimes(1);
  });

  it('handles 409 conflicting decision responses with structured error feedback', () => {
    verificationServiceMock.submitDecision.mockReturnValue(
      throwError(
        () =>
          new HttpErrorResponse({
            status: 409,
            error: {
              error: {
                code: 'DECISION_CONFLICT',
                message: 'Application was already reviewed by another admin.',
                fields: { status: ['Already approved'] },
              },
            },
          })
      )
    );

    const host = fixture.nativeElement as HTMLElement;
    const reviewBtn = Array.from(host.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Review & Confirm')
    );
    reviewBtn?.click();
    fixture.detectChanges();

    const confirmBtn = Array.from(host.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Confirm Decision')
    );
    confirmBtn?.click();
    fixture.detectChanges();

    const alertEl = host.querySelector('[role="alert"]');
    expect(alertEl?.textContent).toContain(
      'Application was already reviewed by another admin. (DECISION_CONFLICT)'
    );
    expect(alertEl?.textContent).toContain('Already approved');
  });

  it('blocks non-admin users via navigationAccessGuard', () => {
    const sessionSignal = signal<NavigationSession>({
      status: 'authenticated',
      account: {
        userId: 5,
        role: 'business_staff',
        isActive: true,
        organizationId: 10,
        membershipActive: true,
        verificationStatus: 'approved',
      },
    });

    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [
        {
          provide: NavigationSessionService,
          useValue: { session: sessionSignal.asReadonly() },
        },
      ],
    });

    const router = TestBed.inject(Router);
    const guard = navigationAccessGuard(['admin']);
    const result = TestBed.runInInjectionContext(() =>
      guard({} as never, {} as never)
    );

    expect(router.serializeUrl(result as ReturnType<Router['createUrlTree']>)).toBe(
      '/unauthorized'
    );
  });
});
