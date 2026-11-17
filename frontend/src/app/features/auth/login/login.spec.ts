import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';

import { Login } from './login';

describe('Login', () => {
  let component: Login;
  let fixture: ComponentFixture<Login>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Login],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();

    fixture = TestBed.createComponent(Login);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
  it.each([
    {
      application: { status: 'pending_verification' },
      expectedMessage: 'Pending Verification. Your application is awaiting admin review.',
    },
    {
      application: {
        status: 'rejected',
        review_note: 'Upload a clearer copy of the registration certificate.',
      },
      expectedMessage:
        'Your organization application was rejected. Upload a clearer copy of the registration certificate. Review the feedback and prepare the requested corrections before resubmitting.',
    },
  ])('shows $application.status and clears the password after login', ({ application, expectedMessage }) => {
    const http = TestBed.inject(HttpTestingController);
    const page = fixture.nativeElement as HTMLElement;

    fixture.componentInstance.form.setValue({
      email: 'Demo@example.com',
      password: 'ExamplePassword123!',
    });
    fixture.detectChanges();

    const button = page.querySelector<HTMLButtonElement>('button[type="submit"]')!;
    button.click();
    fixture.detectChanges();

    expect(button.disabled).toBe(true);

    const request = http.expectOne({
      method: 'POST',
      url: '/api/v1/auth/login',
    });

    expect(request.request.body).toEqual({
      email: 'demo@example.com',
      password: 'ExamplePassword123!',
    });

    request.flush({
      data: {
        access_token: 'test-access-token',
        token_type: 'bearer',
        expires_in: 1800,
        user: {
          user_id: 1,
          email: 'demo@example.com',
          role: 'ngo_staff',
        },
      },
    });

    const applications = http.expectOne({
      method: 'GET',
      url: '/api/v1/organization-applications/me',
    });

    expect(applications.request.headers.get('Authorization'))
      .toBe('Bearer test-access-token');

    applications.flush({
      data: [application],
      pagination: {
        page: 1,
        page_size: 20,
        total_items: 1,
        total_pages: 1,
      },
    });
    fixture.detectChanges();

    expect(page.querySelector('[role="status"]')?.textContent?.trim())
      .toBe(expectedMessage);
    expect(fixture.componentInstance.form.controls.password.value).toBe('');
    expect(button.disabled).toBe(false);
    http.verify();
  });

  it('shows the API error and allows another attempt after a 401', () => {
    const http = TestBed.inject(HttpTestingController);
    const page = fixture.nativeElement as HTMLElement;

    fixture.componentInstance.form.setValue({
      email: 'demo@example.com',
      password: 'WrongPassword123!',
    });
    fixture.detectChanges();

    const button = page.querySelector<HTMLButtonElement>('button[type="submit"]')!;
    button.click();

    const request = http.expectOne({
      method: 'POST',
      url: '/api/v1/auth/login',
    });

    request.flush(
      {
        error: {
          code: 'INVALID_CREDENTIALS',
          message: 'Invalid email or password.',
          fields: [],
        },
      },
      { status: 401, statusText: 'Unauthorized' },
    );
    http.expectNone({
      method: 'GET',
      url: '/api/v1/organization-applications/me',
    });
    fixture.detectChanges();

    expect(page.querySelector('[role="alert"]')?.textContent?.trim())
      .toBe('Invalid email or password.');
    expect(page.querySelector('[role="status"]')).toBeNull();
    expect(button.disabled).toBe(false);
    http.verify();
  });
  it('shows the login validation summary and the email field error', () => {
    const http = TestBed.inject(HttpTestingController);
    const page = fixture.nativeElement as HTMLElement;

    fixture.componentInstance.form.setValue({
      email: 'demo@example.com',
      password: 'ExamplePassword123!',
    });
    fixture.detectChanges();

    page.querySelector<HTMLButtonElement>('button[type="submit"]')!.click();

    http.expectOne({ method: 'POST', url: '/api/v1/auth/login' }).flush(
      {
        error: {
          code: 'VALIDATION_ERROR',
          message: 'Please correct the invalid request fields.',
          fields: [
            {
              field: 'email',
              message: 'Check the email address.',
              code: 'invalid_email',
            },
          ],
        },
      },
      { status: 422, statusText: 'Unprocessable Entity' },
    );
    fixture.detectChanges();

    expect(page.querySelector('[role="alert"]')?.textContent?.trim())
      .toBe('Please correct the invalid request fields.');
    expect(page.querySelector('#login-email-error')?.textContent?.trim())
      .toBe('Check the email address.');
    expect(page.querySelector('#login-email')?.getAttribute('aria-invalid'))
      .toBe('true');

    http.verify();
  });

  function signInWithRejectedApplication(): HttpTestingController {
    const http = TestBed.inject(HttpTestingController);
    component.form.setValue({
      email: 'demo@example.com',
      password: 'ExamplePassword123!',
    });
    component.submit();

    http.expectOne({ method: 'POST', url: '/api/v1/auth/login' }).flush({
      data: {
        access_token: 'test-access-token',
        token_type: 'bearer',
        expires_in: 1800,
        user: { user_id: 1, email: 'demo@example.com', role: 'ngo_staff' },
      },
    });
    http.expectOne({
      method: 'GET',
      url: '/api/v1/organization-applications/me',
    }).flush({
      data: [{
        application_id: 42,
        status: 'rejected',
        review_note: 'Upload a clearer copy of the registration certificate.',
      }],
      pagination: { page: 1, page_size: 20, total_items: 1, total_pages: 1 },
    });
    fixture.detectChanges();
    return http;
  }

  it('resubmits the existing application and displays pending verification', () => {
    const http = signInWithRejectedApplication();
    const page = fixture.nativeElement as HTMLElement;
    const button = page.querySelector<HTMLButtonElement>('#resubmit-application')!;

    expect(button.textContent?.trim()).toBe('Resubmit for review');
    button.click();
    fixture.detectChanges();
    expect(button.disabled).toBe(true);

    const request = http.expectOne({
      method: 'POST',
      url: '/api/v1/organization-applications/42/resubmit',
    });
    expect(request.request.headers.get('Authorization')).toBe('Bearer test-access-token');
    expect(request.request.body).toEqual({});
    expect(page.querySelector('[role="status"]')?.textContent).toContain('was rejected');

    request.flush({ data: { status: 'pending_verification' } });
    fixture.detectChanges();

    expect(page.querySelector('[role="status"]')?.textContent?.trim())
      .toBe('Pending Verification. Your application is awaiting admin review.');
    expect(page.querySelector('#resubmit-application')).toBeNull();
    http.verify();
  });

  it('keeps the rejection feedback and allows retry when resubmission fails', () => {
    const http = signInWithRejectedApplication();
    const page = fixture.nativeElement as HTMLElement;
    const button = page.querySelector<HTMLButtonElement>('#resubmit-application')!;
    const endpoint = { method: 'POST', url: '/api/v1/organization-applications/42/resubmit' };

    button.click();
    http.expectOne(endpoint).flush(
      {
        error: {
          code: 'VALIDATION_ERROR',
          message: 'Upload the corrected certificate before resubmitting.',
          fields: [],
        },
      },
      { status: 422, statusText: 'Unprocessable Entity' },
    );
    fixture.detectChanges();

    expect(page.querySelector('[role="alert"]')?.textContent?.trim())
      .toBe('Upload the corrected certificate before resubmitting.');
    expect(page.querySelector('[role="status"]')?.textContent)
      .toContain('Upload a clearer copy of the registration certificate.');
    expect(button.disabled).toBe(false);

    button.click();
    http.expectOne(endpoint).flush({ data: { status: 'pending_verification' } });
    fixture.detectChanges();

    expect(page.querySelector('[role="alert"]')).toBeNull();
    expect(page.querySelector('[role="status"]')?.textContent).toContain('Pending Verification');
    http.verify();
  });
  function selectCorrection(page: HTMLElement, file: File): HTMLButtonElement {
    const type = page.querySelector<HTMLSelectElement>('#correction-type')!;
    const input = page.querySelector<HTMLInputElement>('#correction-file')!;
    type.value = 'registration_certificate';
    Object.defineProperty(input, 'files', {
      value: { item: (index: number) => index === 0 ? file : null },
    });
    return page.querySelector<HTMLButtonElement>('fieldset button')!;
  }

  it('uploads a corrected document to the rejected application', () => {
    const http = signInWithRejectedApplication();
    const page = fixture.nativeElement as HTMLElement;
    const file = new File(['corrected certificate'], 'certificate.pdf', {
      type: 'application/pdf',
    });

    selectCorrection(page, file).click();
    fixture.detectChanges();
    const resubmit = page.querySelector<HTMLButtonElement>('#resubmit-application')!;
    expect(resubmit.disabled).toBe(true);

    const upload = http.expectOne({
      method: 'POST',
      url: '/api/v1/organization-applications/42/documents',
    });
    expect(upload.request.headers.get('Authorization')).toBe('Bearer test-access-token');
    const body = upload.request.body as FormData;
    expect(body.get('document_type')).toBe('registration_certificate');
    expect(body.get('file')).toBe(file);
    http.expectNone('/api/v1/organization-applications/42/resubmit');

    upload.flush(null, { status: 201, statusText: 'Created' });
    fixture.detectChanges();

    expect(page.textContent).toContain('Corrected document uploaded.');
    expect(page.textContent).toContain('Your organization application was rejected.');
    expect(resubmit.disabled).toBe(false);
    http.verify();
  });

  it('rejects an unsupported corrected file before sending an upload', () => {
    const http = signInWithRejectedApplication();
    const page = fixture.nativeElement as HTMLElement;
    const file = new File(['text'], 'certificate.txt', { type: 'text/plain' });

    selectCorrection(page, file).click();
    fixture.detectChanges();

    expect(page.querySelector('[role="alert"]')?.textContent?.trim())
      .toBe('Choose a PDF, JPG or PNG file.');
    http.expectNone('/api/v1/organization-applications/42/documents');
    http.verify();
  });

});
