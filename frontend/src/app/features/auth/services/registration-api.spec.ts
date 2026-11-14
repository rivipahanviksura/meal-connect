import { HttpErrorResponse, provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { RegistrationApi, RegisterAccountRequest, LoginResponse, CreateNgoApplicationRequest, CreateApplicationResponse } from './registration-api';

describe('RegistrationApi', () => {
  let api: RegistrationApi;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });

    api = TestBed.inject(RegistrationApi);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    http.verify();
  });

  it('posts the account details and forwards a DEC-02 validation error', () => {
    const payload: RegisterAccountRequest = {
      first_name: 'Demo',
      last_name: 'Applicant',
      email: 'demo@example.com',
      password: 'ExamplePassword123!',
      phone: null,
      account_type: 'ngo',
    };

    const response = {
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
    };

    const onError = vi.fn<(error: HttpErrorResponse) => void>();
    api.registerAccount(payload).subscribe({ error: onError });

    const request = http.expectOne({
      method: 'POST',
      url: '/api/v1/auth/register',
    });
    expect(request.request.body).toEqual(payload);

    request.flush(response, {
      status: 422,
      statusText: 'Unprocessable Entity',
    });

    expect(onError).toHaveBeenCalledTimes(1);
    expect(onError).toHaveBeenCalledWith(
      expect.objectContaining({ status: 422, error: response }),
    );
  });
  it('posts the login credentials and returns the access token', () => {
    const credentials = {
      email: 'demo@example.com',
      password: 'ExamplePassword123!',
    };

    const response: LoginResponse = {
      data: {
        access_token: 'test-access-token',
        token_type: 'bearer',
        expires_in: 1800,
        user: {
          user_id: 1,
          email: credentials.email,
          role: 'ngo_staff',
        },
      },
    };

    const onSuccess = vi.fn<(result: LoginResponse) => void>();
    api.login(credentials).subscribe({ next: onSuccess });

    const request = http.expectOne({
      method: 'POST',
      url: '/api/v1/auth/login',
    });
    expect(request.request.body).toEqual(credentials);

    request.flush(response);

    expect(onSuccess).toHaveBeenCalledExactlyOnceWith(response);
  });

  it('forwards the 401 error when the credentials are invalid', () => {
    const response = {
      error: {
        code: 'INVALID_CREDENTIALS',
        message: 'Invalid email or password.',
        fields: [],
      },
    };

    const onSuccess = vi.fn();
    const onError = vi.fn<(error: HttpErrorResponse) => void>();

    api.login({
      email: 'demo@example.com',
      password: 'WrongPassword123!',
    }).subscribe({ next: onSuccess, error: onError });

    const request = http.expectOne({
      method: 'POST',
      url: '/api/v1/auth/login',
    });
    request.flush(response, { status: 401, statusText: 'Unauthorized' });

    expect(onSuccess).not.toHaveBeenCalled();
    expect(onError).toHaveBeenCalledExactlyOnceWith(
      expect.objectContaining({ status: 401, error: response }),
    );
  });
  it('uploads the verification document as authenticated multipart form data', () => {
    const file = new File(['test certificate'], 'certificate.pdf', {
      type: 'application/pdf',
    });

    api.uploadVerificationDocument(
      42,
      'test-access-token',
      'registration_certificate',
      file,
    ).subscribe();

    const request = http.expectOne({
      method: 'POST',
      url: '/api/v1/organization-applications/42/documents',
    });

    expect(request.request.headers.get('Authorization'))
      .toBe('Bearer test-access-token');
    expect(request.request.headers.has('Content-Type')).toBe(false);
    expect(request.request.body).toBeInstanceOf(FormData);

    const body = request.request.body as FormData;
    expect(body.get('document_type')).toBe('registration_certificate');
    expect(body.get('file')).toBe(file);

    request.flush(null, { status: 201, statusText: 'Created' });
  });
  it('creates an authenticated NGO draft and returns its application ID', () => {
    const payload: CreateNgoApplicationRequest = {
      organization_type: 'ngo',
      name: 'Community Relief Foundation',
      registration_number: 'EXAMPLE-123',
      contact_email: 'contact@example.com',
      address_line: 'Example Street',
      city: 'Colombo',
      representative_name: 'Demo Applicant',
    };

    const onSuccess = vi.fn<(result: CreateApplicationResponse) => void>();

    api.createApplication(payload, 'test-access-token')
      .subscribe({ next: onSuccess });

    const request = http.expectOne({
      method: 'POST',
      url: '/api/v1/organization-applications',
    });

    expect(request.request.headers.get('Authorization'))
      .toBe('Bearer test-access-token');
    expect(request.request.body).toEqual(payload);

    const response: CreateApplicationResponse = {
      data: {
        application_id: 42,
        organization_id: 42,
        status: 'draft',
      },
    };

    request.flush(response, { status: 201, statusText: 'Created' });

    expect(onSuccess).toHaveBeenCalledExactlyOnceWith(response);
  });
  it('fetches the authenticated applicant’s applications', () => {
    const response = {
      data: [],
      pagination: {
        page: 1,
        page_size: 20,
        total_items: 0,
        total_pages: 0,
      },
    };
    const onSuccess = vi.fn();

    api.getMyApplications('test-access-token').subscribe({ next: onSuccess });

    const request = http.expectOne({
      method: 'GET',
      url: '/api/v1/organization-applications/me',
    });

    expect(request.request.headers.get('Authorization'))
      .toBe('Bearer test-access-token');

    request.flush(response);

    expect(onSuccess).toHaveBeenCalledExactlyOnceWith(response);
  });
});
