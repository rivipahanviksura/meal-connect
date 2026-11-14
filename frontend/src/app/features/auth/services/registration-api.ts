
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { Api } from '../../../core/services/api';

export type RegistrationAccountType = 'business' | 'ngo';

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  data: {
    access_token: string;
    token_type: 'bearer';
    expires_in: number;
    user: {
      user_id: number;
      email: string;
      role: string;
    };
  };
}

/**
 * Approved MEAL-80 / DEC-05 public registration payload.
 *
 * Security roles are assigned by the backend.
 * Never include role or account_status in this request.
 */
export interface RegisterAccountRequest {
  first_name: string;
  last_name: string;
  email: string;
  password: string;
  phone: string | null;
  account_type: RegistrationAccountType;
}

/**
 * Canonical DEC-02 API error structure.
 */
export interface ApiFieldError {
  field: string;
  message: string;
  code: string;
}

export interface ApiErrorResponse {
  error: {
    code: string;
    message: string;
    fields: ApiFieldError[];
  };
}

export function parseRegistrationApiError(
  response: unknown
): ApiErrorResponse | null {
  if (
    typeof response !== 'object' ||
    response === null ||
    !('error' in response)
  ) {
    return null;
  }

  const error = response.error;

  if (
    typeof error !== 'object' ||
    error === null ||
    !('code' in error) ||
    typeof error.code !== 'string' ||
    !('message' in error) ||
    typeof error.message !== 'string' ||
    !('fields' in error) ||
    !Array.isArray(error.fields)
  ) {
    return null;
  }

  const validFields: ApiFieldError[] = error.fields.filter(
    (field: unknown): field is ApiFieldError =>
      typeof field === 'object' &&
      field !== null &&
      'field' in field &&
      typeof field.field === 'string' &&
      'message' in field &&
      typeof field.message === 'string' &&
      'code' in field &&
      typeof field.code === 'string'
  );

  return {
    error: {
      code: error.code,
      message: error.message,
      fields: validFields
    }
  };
}

export type RegistrationAccountField =
  | 'firstName'
  | 'lastName'
  | 'email'
  | 'password'
  | 'phone';

const registrationFieldMap: Record<string, RegistrationAccountField> = {
  first_name: 'firstName',
  last_name: 'lastName',
  email: 'email',
  password: 'password',
  phone: 'phone'
};

export function mapRegistrationFieldError(
  backendField: string
): RegistrationAccountField | null {
  return Object.prototype.hasOwnProperty.call(
    registrationFieldMap,
    backendField
  )
    ? registrationFieldMap[backendField]
    : null;
}

@Injectable({
  providedIn: 'root'
})
export class RegistrationApiService {
  private readonly api = inject(Api);

  /**
   * POST /api/v1/auth/register
   *
   * The successful response schema is pending
   * final verification against MEAL-77.
   *
   * This method must not be called until backend
   * contract compatibility has been confirmed.
   */
  registerAccount(
    request: RegisterAccountRequest
  ): Observable<unknown> {
    return this.api.post<unknown>(
      'auth/register',
      request
    );
  }
}

interface ApplicationDetails {
  name: string;
  registration_number?: string;
  contact_email: string;
  contact_phone?: string;
  address_line: string;
  city: string;
  district?: string;
  representative_name: string;
}

export interface CreateNgoApplicationRequest extends ApplicationDetails {
  organization_type: 'ngo';
}

export interface CreateBusinessApplicationRequest extends ApplicationDetails {
  organization_type: 'business';
  // Confirm the JSON key against the backend schema when the endpoint is implemented.
  business_subtype: 'restaurant' | 'bakery';
}

export type CreateApplicationRequest =
  | CreateNgoApplicationRequest
  | CreateBusinessApplicationRequest;

export interface CreateApplicationResponse {
  data: {
    application_id: number;
    organization_id: number;
    status: 'draft';
  };
}

export interface MyApplicationsResponse {
  data: unknown[];
  pagination: {
    page: number;
    page_size: number;
    total_items: number;
    total_pages: number;
  };
}

@Injectable({ providedIn: 'root' })
export class RegistrationApi {
  private readonly api = inject(Api);

  registerAccount(request: RegisterAccountRequest) {
    return this.api.post<unknown>('auth/register', request);
  }
  login(request: LoginRequest) {
    return this.api.post<LoginResponse>('auth/login', request);
  }
  uploadVerificationDocument(
    applicationId: number,
    accessToken: string,
    documentType: string,
    file: File,
  ) {
    const body = new FormData();
    body.append('file', file);
    body.append('document_type', documentType);

    return this.api.post<unknown>(
      `organization-applications/${applicationId}/documents`,
      body,
      { headers: { Authorization: `Bearer ${accessToken}` } },
    );
  }
  submitApplication(applicationId: number, accessToken: string) {
    return this.api.post<{ data: { status: 'pending_verification' } }>(
      `organization-applications/${applicationId}/submit`,
      {},
      { headers: { Authorization: `Bearer ${accessToken}` } },
    );
  }
  resubmitApplication(applicationId: number, accessToken: string) {
    return this.api.post<{ data: { status: 'pending_verification' } }>(
      `organization-applications/${applicationId}/resubmit`,
      {},
      { headers: { Authorization: `Bearer ${accessToken}` } },
    );
  }
  getMyApplications(accessToken: string) {
    return this.api.get<MyApplicationsResponse>(
      'organization-applications/me',
      { headers: { Authorization: `Bearer ${accessToken}` } },
    );
  }
  createApplication(
    request: CreateApplicationRequest,
    accessToken: string,
  ) {
    return this.api.post<CreateApplicationResponse>(
      'organization-applications',
      request,
      { headers: { Authorization: `Bearer ${accessToken}` } },
    );
  }
}
