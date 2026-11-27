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
    uploadDocument: ReturnType<typeof vi.fn>;
    resubmitApplication: ReturnType<typeof vi.fn>;
    getApplicationById: ReturnType<typeof vi.fn>;
    submitDecision: ReturnType<typeof vi.fn>;
  };

  beforeEach(async () => {
    verificationServiceMock = {
      getMyApplications: vi.fn(),
      uploadDocument: vi.fn(),
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
            organization_name: 'Green Valley Foods',
            verification_status: 'request_corrections',
            review_note: 'Missing business license',
          },
        ],
      })
    );
    verificationServiceMock.resubmitApplication.mockReturnValue(
      of({ verification_status: 'pending' })
    );

    fixture = TestBed.createComponent(OrganizationFeedback);
    fixture.detectChanges();

    const host = fixture.nativeElement as HTMLElement;
    expect(host.textContent).toContain('Green Valley Foods');
    expect(host.textContent).toContain('Missing business license');
    expect(host.textContent).toContain(
      'Protected organization features remain locked until verification is approved.'
    );
    expect(host.querySelector('#correction-note')).toBeNull();

    const resubmitBtn = Array.from(host.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Resubmit Application')
    );
    resubmitBtn?.click();
    fixture.detectChanges();

    expect(verificationServiceMock.uploadDocument).not.toHaveBeenCalled();
    expect(verificationServiceMock.resubmitApplication).toHaveBeenCalledWith(22);
    expect(host.textContent).toContain('Application resubmitted for verification.');
  });

  it('uploads selected document with constrained document type before resubmitting application', () => {
    const callOrder: string[] = [];

    verificationServiceMock.getMyApplications.mockReturnValue(
      of({
        data: [
          {
            application_id: 22,
            organization_id: 8,
            organization_name: 'Green Valley Foods',
            verification_status: 'rejected',
            review_note: 'Please upload valid registration proof',
          },
        ],
      })
    );
    verificationServiceMock.uploadDocument.mockImplementation(() => {
      callOrder.push('uploadDocument');
      return of({ document_id: 99 });
    });
    verificationServiceMock.resubmitApplication.mockImplementation(() => {
      callOrder.push('resubmitApplication');
      return of({ verification_status: 'pending' });
    });

    fixture = TestBed.createComponent(OrganizationFeedback);
    fixture.detectChanges();

    const host = fixture.nativeElement as HTMLElement;
    const typeSelect = host.querySelector(
      '#correction-document-type'
    ) as HTMLSelectElement;
    const optionValues = Array.from(typeSelect.options).map((o) => o.value);
    expect(optionValues).toEqual([
      'registration_certificate',
      'representative_authorization',
      'supporting_document',
    ]);

    typeSelect.value = 'registration_certificate';
    typeSelect.dispatchEvent(new Event('change'));
    fixture.detectChanges();

    const fileInput = host.querySelector('#correction-document') as HTMLInputElement;
    const file = new File(['dummy content'], 'business-license.pdf', {
      type: 'application/pdf',
    });

    Object.defineProperty(fileInput, 'files', {
      value: [file],
      configurable: true,
    });
    fileInput.dispatchEvent(new Event('change'));
    fixture.detectChanges();

    const resubmitBtn = Array.from(host.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Resubmit Application')
    );
    resubmitBtn?.click();
    fixture.detectChanges();

    expect(verificationServiceMock.uploadDocument).toHaveBeenCalledWith(
      22,
      file,
      'registration_certificate'
    );
    expect(verificationServiceMock.resubmitApplication).toHaveBeenCalledWith(22);
    expect(callOrder).toEqual(['uploadDocument', 'resubmitApplication']);
    expect(host.textContent).toContain(
      'Document uploaded and application resubmitted for verification.'
    );
  });

  it('displays unlocked status message when organization is approved', () => {
    verificationServiceMock.getMyApplications.mockReturnValue(
      of({
        data: [
          {
            application_id: 22,
            organization_id: 8,
            organization_name: 'Green Valley Foods',
            verification_status: 'approved',
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
