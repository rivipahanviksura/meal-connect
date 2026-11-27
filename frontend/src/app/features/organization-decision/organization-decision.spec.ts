import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HttpErrorResponse } from '@angular/common/http';
import { ActivatedRoute, convertToParamMap, Router } from '@angular/router';
import { of, Subject, throwError } from 'rxjs';
import { signal } from '@angular/core';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { OrganizationDecision } from './organization-decision';
import { OrganizationVerificationService } from '../../core/services/organization-verification.service';
import {
  DecisionResponsePayload,
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
    application_id: 101,
    id: 101,
    organization_id: 12,
    organization_name: 'Hope Kitchen',
    organization_type: 'NGO',
    verification_status: 'pending',
    status: 'pending',
    documents: [
      {
        document_id: 1,
        original_filename: 'registration.pdf',
        review_status: 'submitted',
      },
    ],
    status_history: [],
  };

  const validReviewNote = 'Verified registration documents and organization details.';

  function setReviewNote(value: string): void {
    const textarea = fixture.nativeElement.querySelector(
      '#decision-review-note'
    ) as HTMLTextAreaElement;
    textarea.value = value;
    textarea.dispatchEvent(new Event('input'));
    fixture.detectChanges();
  }

  function clickButtonByText(text: string): void {
    const host = fixture.nativeElement as HTMLElement;
    const btn = Array.from(host.querySelectorAll('button')).find((b) =>
      b.textContent?.includes(text)
    );
    btn?.click();
    fixture.detectChanges();
  }

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

  it('loads wrapped application details including documents and status history', () => {
    const host = fixture.nativeElement as HTMLElement;
    expect(verificationServiceMock.getApplicationById).toHaveBeenCalledWith('101');
    expect(host.textContent).toContain('Hope Kitchen');
    expect(host.textContent).toContain('pending');
    expect(host.textContent).toContain('registration.pdf');
    expect(host.textContent).toContain('No status history recorded yet.');
  });

  it('renders backend status history fields (new_status, change_reason, changed_by_name, changed_at)', () => {
    verificationServiceMock.getApplicationById.mockReturnValue(
      of({
        ...mockApplication,
        status_history: [
          {
            id: 501,
            new_status: 'request_corrections',
            change_reason: 'Please attach official NGO certificate.',
            changed_by_name: 'Admin User',
            changed_at: '2026-11-27T10:30:00Z',
          },
        ],
      })
    );

    const localFixture = TestBed.createComponent(OrganizationDecision);
    localFixture.detectChanges();

    const host = localFixture.nativeElement as HTMLElement;
    expect(host.textContent).toContain('request_corrections');
    expect(host.textContent).toContain('Please attach official NGO certificate.');
    expect(host.textContent).toContain('Admin User');
    expect(host.textContent).toContain('2026-11-27T10:30:00Z');
  });

  it('requires at least 10 characters for review_note even when approving', () => {
    const host = fixture.nativeElement as HTMLElement;
    clickButtonByText('Approve');
    setReviewNote('Too short');
    clickButtonByText('Review & Confirm');

    expect(host.textContent).toContain('at least 10 characters');
    expect(verificationServiceMock.submitDecision).not.toHaveBeenCalled();
  });

  it('approves an organization application with decision and review_note after confirmation', () => {
    const response: DecisionResponsePayload = {
      data: {
        application_id: 101,
        verification_status: 'approved',
        review_note: validReviewNote,
      },
      message: 'Decision "approved" submitted successfully.',
    };
    verificationServiceMock.submitDecision.mockReturnValue(of(response));

    const host = fixture.nativeElement as HTMLElement;
    clickButtonByText('Approve');
    setReviewNote(validReviewNote);
    clickButtonByText('Review & Confirm');
    clickButtonByText('Confirm Decision');

    expect(verificationServiceMock.submitDecision).toHaveBeenCalledWith('101', {
      decision: 'approved',
      review_note: validReviewNote,
    });
    expect(host.textContent).toContain('Decision "approved" submitted successfully.');
  });

  it('submits rejection with decision "rejected" and review_note', () => {
    verificationServiceMock.submitDecision.mockReturnValue(
      of({
        data: {
          application_id: 101,
          verification_status: 'rejected',
          review_note: 'Incomplete registration certificate provided.',
        },
      })
    );

    clickButtonByText('Reject');
    setReviewNote('Incomplete registration certificate provided.');
    clickButtonByText('Review & Confirm');
    clickButtonByText('Confirm Decision');

    expect(verificationServiceMock.submitDecision).toHaveBeenCalledWith('101', {
      decision: 'rejected',
      review_note: 'Incomplete registration certificate provided.',
    });
  });

  it('submits a correction request with decision "request_corrections" and review_note', () => {
    verificationServiceMock.submitDecision.mockReturnValue(
      of({
        data: {
          application_id: 101,
          verification_status: 'request_corrections',
          review_note: 'Please upload a clearer tax registration document.',
        },
      })
    );

    clickButtonByText('Request Corrections');
    setReviewNote('Please upload a clearer tax registration document.');
    clickButtonByText('Review & Confirm');
    clickButtonByText('Confirm Decision');

    expect(verificationServiceMock.submitDecision).toHaveBeenCalledWith('101', {
      decision: 'request_corrections',
      review_note: 'Please upload a clearer tax registration document.',
    });
  });

  it('resets confirmation if action or review_note changes before final submission', () => {
    const host = fixture.nativeElement as HTMLElement;
    setReviewNote(validReviewNote);
    clickButtonByText('Review & Confirm');

    expect(host.querySelector('[aria-label="Confirm decision"]')).not.toBeNull();

    setReviewNote('Updated review note with more than ten characters.');
    expect(host.querySelector('[aria-label="Confirm decision"]')).toBeNull();
  });

  it('prevents duplicate submissions while a request is in flight', () => {
    const pending$ = new Subject<DecisionResponsePayload>();
    verificationServiceMock.submitDecision.mockReturnValue(pending$.asObservable());

    setReviewNote(validReviewNote);
    clickButtonByText('Review & Confirm');
    clickButtonByText('Confirm Decision');
    clickButtonByText('Confirm Decision');

    expect(verificationServiceMock.submitDecision).toHaveBeenCalledTimes(1);
  });

  it('handles 403 authorization errors when submitting a decision', () => {
    verificationServiceMock.submitDecision.mockReturnValue(
      throwError(
        () =>
          new HttpErrorResponse({
            status: 403,
            error: {
              error: {
                code: 'FORBIDDEN',
                message: 'Admin role is required to submit decisions.',
              },
            },
          })
      )
    );

    const host = fixture.nativeElement as HTMLElement;
    setReviewNote(validReviewNote);
    clickButtonByText('Review & Confirm');
    clickButtonByText('Confirm Decision');

    const alertEl = host.querySelector('[role="alert"]');
    expect(alertEl?.textContent).toContain(
      'Admin role is required to submit decisions. (FORBIDDEN)'
    );
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
    setReviewNote(validReviewNote);
    clickButtonByText('Review & Confirm');
    clickButtonByText('Confirm Decision');

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
