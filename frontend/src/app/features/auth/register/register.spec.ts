import { ComponentFixture, TestBed } from '@angular/core/testing';

import type { CreateApplicationRequest } from '../services/registration-api';
import { Register, type SelectedVerificationDocument } from './register';
import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';


describe('Register', () => {
  let component: Register;
  let fixture: ComponentFixture<Register>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Register],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();

    fixture = TestBed.createComponent(Register);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
  it('shows the API error summary and the email field error after a 422 response', () => {
    const fixture = TestBed.createComponent(Register);
    const component = fixture.componentInstance;
    const page = fixture.nativeElement as HTMLElement;
    const http = TestBed.inject(HttpTestingController);

    component.selectAccountType('ngo');
    component.accountForm.patchValue({
      firstName: 'Demo',
      lastName: 'Applicant',
      email: 'demo@example.com',
      password: 'ExamplePassword123!',
      confirmPassword: 'ExamplePassword123!',
    });
    component.currentStep.set(4);

    component.registerAccount();

    const request = http.expectOne({
      method: 'POST',
      url: '/api/v1/auth/register',
    });

    request.flush(
      {
        error: {
          code: 'VALIDATION_ERROR',
          message: 'Please correct the invalid request fields.',
          fields: [
            {
              field: 'email',
              message: 'Enter a valid email address.',
              code: 'invalid_email',
            },
          ],
        },
      },
      { status: 422, statusText: 'Unprocessable Entity' },
    );

    fixture.detectChanges();

    expect(component.currentStep()).toBe(1);
    expect(component.isRegisteringAccount()).toBe(false);
    expect(component.accountCreated()).toBe(false);
    expect(page.querySelector('#registration-api-error')?.textContent?.trim())
      .toBe('Please correct the invalid request fields.');
    expect(page.querySelector('#email-error')?.textContent?.trim())
      .toBe('Enter a valid email address.');
    expect(page.querySelector('#email')?.getAttribute('aria-invalid'))
      .toBe('true');
    expect(component.accountForm.controls.email.value).toBe('demo@example.com');

    http.verify();
  });
  it('marks the account as created after 201 and prevents duplicate requests', () => {
    const fixture = TestBed.createComponent(Register);
    const component = fixture.componentInstance;
    const http = TestBed.inject(HttpTestingController);
    const endpoint = '/api/v1/auth/register';

    component.selectAccountType('ngo');
    component.accountForm.patchValue({
      firstName: 'Demo',
      lastName: 'Applicant',
      email: 'demo@example.com',
      password: 'ExamplePassword123!',
      confirmPassword: 'ExamplePassword123!',
    });
    component.currentStep.set(4);

    component.registerAccount();
    component.registerAccount();

    const request = http.expectOne({ method: 'POST', url: endpoint });

    expect(component.isRegisteringAccount()).toBe(true);
    expect(component.accountCreated()).toBe(false);

    request.flush(null, { status: 201, statusText: 'Created' });

    expect(component.isRegisteringAccount()).toBe(false);
    expect(component.accountCreated()).toBe(true);
    expect(component.registrationError()).toBeNull();

    component.registerAccount();
    http.expectNone({ method: 'POST', url: endpoint });
    http.verify();
  });

  function startNgoSubmission(
    http: HttpTestingController,
    page: HTMLElement,
    additionalDocuments: SelectedVerificationDocument[] = [],
  ): File {
    component.ngoForm.setValue({
      ngoName: 'Community Relief Foundation',
      registrationNumber: 'EXAMPLE-123',
      registrationAuthority: 'Example Registration Authority',
      registrationDate: '2020-01-01',
      registeredAddress: '10 Example Street',
      city: 'Colombo',
      operatingArea: 'Western Province',
      contactEmail: 'contact@example.com',
      contactPhone: '0112345678',
      representativeDesignation: 'Coordinator',
      distributionArea: 'Colombo District',
      operationalCapability: 'Local food distribution',
    });

    return startSubmission(http, page, {
      organization_type: 'ngo',
      name: 'Community Relief Foundation',
      registration_number: 'EXAMPLE-123',
      contact_email: 'contact@example.com',
      contact_phone: '0112345678',
      address_line: '10 Example Street',
      city: 'Colombo',
      representative_name: 'Demo Applicant',
    }, additionalDocuments);
  }

  function startSubmission(
    http: HttpTestingController,
    page: HTMLElement,
    application: CreateApplicationRequest,
    additionalDocuments: SelectedVerificationDocument[] = [],
  ): File {
    component.selectAccountType(application.organization_type);
    component.accountForm.setValue({
      firstName: 'Demo',
      lastName: 'Applicant',
      email: 'demo@example.com',
      password: 'ExamplePassword123!',
      confirmPassword: 'ExamplePassword123!',
      phone: '',
    });

    const certificate = new File(['test certificate'], 'certificate.pdf', {
      type: 'application/pdf',
    });

    component.selectedDocuments.set([
      { type: 'registration_certificate', file: certificate },
      ...additionalDocuments,
    ]);
    component.setInformationDeclaration(true);
    component.setVerificationDeclaration(true);
    component.currentStep.set(4);
    fixture.detectChanges();

    const submitButton = Array.from(page.querySelectorAll('button')).find(
      (button) => button.textContent?.trim() === 'Submit Application',
    );

    expect(submitButton?.disabled).toBe(false);
    submitButton!.click();

    const register = http.expectOne({
      method: 'POST',
      url: '/api/v1/auth/register',
    });
    expect(register.request.body.account_type).toBe(application.organization_type);
    register.flush(null, { status: 201, statusText: 'Created' });

    const login = http.expectOne({
      method: 'POST',
      url: '/api/v1/auth/login',
    });
    expect(login.request.body).toEqual({
      email: 'demo@example.com',
      password: 'ExamplePassword123!',
    });
    login.flush({
      data: {
        access_token: 'test-access-token',
        token_type: 'bearer',
        expires_in: 1800,
        user: {
          user_id: 1,
          email: 'demo@example.com',
          role: application.organization_type === 'ngo' ? 'ngo_staff' : 'business_staff',
        },
      },
    });

    const draft = http.expectOne({
      method: 'POST',
      url: '/api/v1/organization-applications',
    });
    expect(draft.request.headers.get('Authorization'))
      .toBe('Bearer test-access-token');
    expect(draft.request.body).toEqual(application);
    draft.flush(
      { data: { application_id: 42, organization_id: 42, status: 'draft' } },
      { status: 201, statusText: 'Created' },
    );

    return certificate;
  }

  it('submits an NGO application and shows Pending Verification after confirmation', () => {
    const page = fixture.nativeElement as HTMLElement;
    const http = TestBed.inject(HttpTestingController);
    const certificate = startNgoSubmission(http, page);

    expectSubmittedApplication(http, page, certificate);
  });

  it.each(['restaurant', 'bakery'] as const)(
    'submits a %s application and shows Pending Verification after confirmation',
    (businessType) => {
      const page = fixture.nativeElement as HTMLElement;
      const http = TestBed.inject(HttpTestingController);

      component.businessForm.setValue({
        businessName: 'Example Food Business',
        registrationNumber: 'EXAMPLE-456',
        businessType,
        registeredAddress: '20 Example Street',
        city: 'Colombo',
        pickupLocation: 'Rear entrance',
        contactEmail: 'business@example.com',
        contactPhone: '0112345678',
        representativeDesignation: 'Owner',
      });

      const certificate = startSubmission(http, page, {
        organization_type: 'business',
        business_subtype: businessType,
        name: 'Example Food Business',
        registration_number: 'EXAMPLE-456',
        contact_email: 'business@example.com',
        contact_phone: '0112345678',
        address_line: '20 Example Street',
        city: 'Colombo',
        representative_name: 'Demo Applicant',
      });

      expectSubmittedApplication(http, page, certificate);
    },
  );

  function expectSubmittedApplication(
    http: HttpTestingController,
    page: HTMLElement,
    certificate: File,
  ): void {
    const upload = http.expectOne({
      method: 'POST',
      url: '/api/v1/organization-applications/42/documents',
    });
    const uploadBody = upload.request.body as FormData;
    expect(uploadBody.get('document_type')).toBe('registration_certificate');
    expect(uploadBody.get('file')).toBe(certificate);

    const submitEndpoint = {
      method: 'POST',
      url: '/api/v1/organization-applications/42/submit',
    };
    http.expectNone(submitEndpoint);

    upload.flush(null, { status: 201, statusText: 'Created' });

    const submit = http.expectOne(submitEndpoint);
    expect(submit.request.headers.get('Authorization'))
      .toBe('Bearer test-access-token');
    expect(submit.request.body).toEqual({});
    fixture.detectChanges();

    expect(component.applicationSubmitted()).toBe(false);
    expect(page.textContent).not.toContain('Application submitted. Pending Verification.');

    submit.flush({ data: { status: 'pending_verification' } });
    fixture.detectChanges();

    expect(component.applicationSubmitted()).toBe(true);
    expect(component.isSubmittingApplication()).toBe(false);
    expect(page.textContent).toContain('Application submitted. Pending Verification.');
    expect(component.accountForm.controls.password.value).toBe('');
    expect(component.selectedDocuments()).toEqual([]);

    http.verify();
  }

  it.each([
    { status: 503, statusText: 'Service Unavailable' },
    { status: 422, statusText: 'Unprocessable Entity' },
  ])('retries only the failed document upload on the existing draft after $status', ({ status, statusText }) => {
    const page = fixture.nativeElement as HTMLElement;
    const http = TestBed.inject(HttpTestingController);
    const authorization = new File(['test authorization'], 'authorization.pdf', {
      type: 'application/pdf',
    });
    const certificate = startNgoSubmission(http, page, [
      { type: 'representative_authorization', file: authorization },
    ]);

    const documentEndpoint = {
      method: 'POST',
      url: '/api/v1/organization-applications/42/documents',
    };
    const submitEndpoint = {
      method: 'POST',
      url: '/api/v1/organization-applications/42/submit',
    };
    const firstUpload = http.expectOne(documentEndpoint);
    expect((firstUpload.request.body as FormData).get('file')).toBe(certificate);
    firstUpload.flush(null, { status: 201, statusText: 'Created' });

    const failedUpload = http.expectOne(documentEndpoint);
    expect((failedUpload.request.body as FormData).get('file')).toBe(authorization);
    failedUpload.flush(
      {
        error: {
          code: 'UPLOAD_FAILED',
          message: 'The document upload failed. Please try again.',
          fields: [],
        },
      },
      { status, statusText },
    );
    fixture.detectChanges();

    http.expectNone(submitEndpoint);
    expect(component.applicationSubmitted()).toBe(false);
    const alerts = Array.from(page.querySelectorAll('[role="alert"]'));
    expect(alerts.map((alert) => alert.textContent?.trim()))
      .toContain('The document upload failed. Please try again.');

    let fileToRetry = authorization;
    if (status === 422) {
      const findButton = (label: string) => Array.from(page.querySelectorAll('button')).find(
        (button) => button.textContent?.trim() === label,
      );

      expect(findButton('Back to Documents')?.disabled).toBe(false);
      findButton('Back to Documents')!.click();
      fixture.detectChanges();

      expect(findButton('Back')?.disabled).toBe(true);
      expect(page.querySelector<HTMLInputElement>('#registrationCertificate')?.disabled)
        .toBe(true);
      expect(page.querySelector<HTMLButtonElement>('[aria-label="Remove registration certificate"]')?.disabled)
        .toBe(true);

      const input = page.querySelector<HTMLInputElement>('#representativeAuthorization')!;
      expect(input.disabled).toBe(false);
      expect(page.querySelector<HTMLButtonElement>('[aria-label="Remove authorization document"]')?.disabled)
        .toBe(false);

      const replacement = new File(['corrected authorization'], 'corrected.pdf', {
        type: 'application/pdf',
      });
      Object.defineProperty(input, 'files', {
        value: { item: (index: number) => index === 0 ? replacement : null },
      });
      input.dispatchEvent(new Event('change'));
      fixture.detectChanges();

      expect(page.textContent).toContain('corrected.pdf');
      fileToRetry = replacement;
      findButton('Continue to Review')!.click();
      fixture.detectChanges();
    }

    const retryButton = Array.from(page.querySelectorAll('button')).find(
      (button) => button.textContent?.trim() === 'Submit Application',
    );
    expect(retryButton?.disabled).toBe(false);
    retryButton!.click();

    http.expectNone({ method: 'POST', url: '/api/v1/auth/register' });
    const retryLogin = http.expectOne({
      method: 'POST',
      url: '/api/v1/auth/login',
    });
    retryLogin.flush({
      data: {
        access_token: 'retry-access-token',
        token_type: 'bearer',
        expires_in: 1800,
        user: {
          user_id: 1,
          email: 'demo@example.com',
          role: 'ngo_staff',
        },
      },
    });
    http.expectNone({ method: 'POST', url: '/api/v1/organization-applications' });

    const retriedUpload = http.expectOne(documentEndpoint);
    const retryBody = retriedUpload.request.body as FormData;
    expect(retriedUpload.request.headers.get('Authorization'))
      .toBe('Bearer retry-access-token');
    expect(retryBody.get('document_type')).toBe('representative_authorization');
    expect(retryBody.get('file')).toBe(fileToRetry);
    http.expectNone(submitEndpoint);

    retriedUpload.flush(null, { status: 201, statusText: 'Created' });
    http.expectNone(documentEndpoint);

    const submit = http.expectOne(submitEndpoint);
    expect(submit.request.headers.get('Authorization')).toBe('Bearer retry-access-token');
    submit.flush({ data: { status: 'pending_verification' } });
    fixture.detectChanges();

    expect(component.applicationSubmitted()).toBe(true);
    expect(component.isSubmittingApplication()).toBe(false);
    expect(page.textContent).toContain('Application submitted. Pending Verification.');
    http.verify();
  });
});
