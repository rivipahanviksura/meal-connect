import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { Api } from './api';
import {
  DecisionRequestPayload,
  MyApplicationsResponse,
  OrganizationApplicationDetail,
} from '../models/navigation-account';

@Injectable({
  providedIn: 'root',
})
export class OrganizationVerificationService {
  private readonly api = inject(Api);

  getMyApplications(): Observable<MyApplicationsResponse> {
    return this.api.get<MyApplicationsResponse>('/organization-applications/me');
  }

  resubmitApplication(applicationId: number): Observable<unknown> {
    return this.api.post(`/organization-applications/${applicationId}/resubmit`, {});
  }

  getApplicationById(applicationId: number | string): Observable<OrganizationApplicationDetail> {
    return this.api.get<OrganizationApplicationDetail>(
      `/admin/organization-applications/${applicationId}`
    );
  }

  submitDecision(
    applicationId: number | string,
    payload: DecisionRequestPayload
  ): Observable<OrganizationApplicationDetail> {
    return this.api.post<OrganizationApplicationDetail>(
      `/admin/organization-applications/${applicationId}/decision`,
      payload
    );
  }
}
