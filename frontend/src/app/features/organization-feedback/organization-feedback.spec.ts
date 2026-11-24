import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HttpErrorResponse } from '@angular/common/http';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { OrganizationFeedback } from './organization-feedback';
import { OrganizationVerificationService } from '../../core/services/organization-verification.service';

describe('OrganizationFeedback', () => {
  let fixture: ComponentFixture<OrganizationFeedback>;
  let verificationServiceMock: {
    getMyApplications: ReturnType<typeof vi.fn>;
    resubmitApplication: ReturnType<typeof vi.fn>;
    getApplicationById: ReturnType<typeof vi.fn>;
    submitDecision: ReturnType<typeof vi.fn>;
  };

  beforeEach(async () => {
    verificationServiceMock = {
      getMyApplications: vi.fn(),
      resubmitApplication: vi.fn(),
      getApplicationById: vi.fn(),
      submitDecision: vi.fn(),
    };

    await TestBed.configureTestingModule({
      imports: [OrganizationFeedback],
      providers: [
        provideRouter([]),
        { provide: OrganizationVerificationService, useValue: verificationServiceMock },
      ],
    }).compileComponents();
  });

  it('displays reviewer feedback and allows resubmission when rejected or corrections requested', () => {
    verificationServiceMock.getMyApplications.mockReturnValue(
      of({
        data: [
          {
            application_id: 22,
            organization_id: 8,
            name: 'Green Valley Foods',
            status: 'rejected',
            review_note: 'Missing business license',
          },
        ],
      })
    );
    verificationServiceMock.resubmitApplication.mockReturnValue(of({ status: 'pending' }));

    fixture = TestBed.createComponent(OrganizationFeedback);
    fixture.detectChanges();

    const host = fixture.nativeElement as HTMLElement;
    expect(host.textContent).toContain('Missing business license');
    expect(host.textContent).toContain(
      'Protected organization features remain locked until verification is approved.'
    );

    const resubmitBtn = Array.from(host.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Resubmit Application')
    );
    resubmitBtn?.click();
    fixture.detectChanges();

    expect(verificationServiceMock.resubmitApplication).toHaveBeenCalledWith(22);
    expect(host.textContent).toContain('Application resubmitted for verification.');
  });

  it('displays unlocked status message when organization is approved', () => {
    verificationServiceMock.getMyApplications.mockReturnValue(
      of({
        data: [
          {
            application_id: 22,
            organization_id: 8,
            name: 'Green Valley Foods',
            status: 'approved',
          },
        ],
      })
    );

    fixture = TestBed.createComponent(OrganizationFeedback);
    fixture.detectChanges();

    const host = fixture.nativeElement as HTMLElement;
    expect(host.textContent).toContain(
      'Your organization is verified. Protected features are now available.'
    );
  });

  it('renders structured 403 unauthorized error details when fetching status fails', () => {
    verificationServiceMock.getMyApplications.mockReturnValue(
      throwError(
        () =>
          new HttpErrorResponse({
            status: 403,
            error: {
              error: {
                code: 'FORBIDDEN_ORG_ACCESS',
                message: 'Access denied for this organization.',
              },
            },
          })
      )
    );

    fixture = TestBed.createComponent(OrganizationFeedback);
    fixture.detectChanges();

    const host = fixture.nativeElement as HTMLElement;
    const alertEl = host.querySelector('[role="alert"]');
    expect(alertEl?.textContent).toContain(
      'Access denied for this organization. (FORBIDDEN_ORG_ACCESS)'
    );
  });
});
