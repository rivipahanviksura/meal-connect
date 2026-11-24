import { inject, Injectable } from '@angular/core';
import { map, Observable } from 'rxjs';
import { Api } from './api';
import {
  DecisionRequestPayload,
  MyApplicationsResponse,
  OrganizationApplicationDetail,
  OrganizationApplicationDetailResponse,
} from '../models/navigation-account';

@Injectable({
  providedIn: 'root',
})
export class OrganizationVerificationService {
  private readonly api = inject(Api);

  getMyApplications(): Observable<MyApplicationsResponse> {
    return this.api.get<MyApplicationsResponse>('/organization-applications/me');
  }

  resubmitApplication(applicationId: number | string): Observable<unknown> {
    return this.api.post(`/organization-applications/${applicationId}/resubmit`, {});
  }

  getApplicationById(
    applicationId: number | string
  ): Observable<OrganizationApplicationDetail> {
    return this.api
      .get<OrganizationApplicationDetail | OrganizationApplicationDetailResponse>(
        `/admin/organization-applications/${applicationId}`
      )
      .pipe(
        map((res) =>
          res && typeof res === 'object' && 'data' in res && res.data
            ? res.data
            : (res as OrganizationApplicationDetail)
        )
      );
  }

  submitDecision(
    applicationId: number | string,
    payload: DecisionRequestPayload
  ): Observable<OrganizationApplicationDetail> {
    const normalizedPayload: DecisionRequestPayload = {
      action: payload.action,
      ...(payload.reason?.trim() ? { reason: payload.reason.trim() } : {}),
      ...(payload.internal_comment?.trim()
        ? { internal_comment: payload.internal_comment.trim() }
        : {}),
    };

    return this.api
      .post<OrganizationApplicationDetail | OrganizationApplicationDetailResponse>(
        `/admin/organization-applications/${applicationId}/decision`,
        normalizedPayload
      )
      .pipe(
        map((res) =>
          res && typeof res === 'object' && 'data' in res && res.data
            ? res.data
            : (res as OrganizationApplicationDetail)
        )
      );
  }
}
