import { inject, Injectable } from '@angular/core';
import { map, Observable } from 'rxjs';
import { Api } from './api';
import {
  BackendDocumentType,
  DecisionRequestPayload,
  DecisionResponsePayload,
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

  uploadDocument(
    applicationId: number | string,
    file: File,
    documentType: BackendDocumentType
  ): Observable<unknown> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('document_type', documentType);

    return this.api.post(
      `/organization-applications/${applicationId}/documents`,
      formData
    );
  }

  resubmitApplication(
    applicationId: number | string
  ): Observable<unknown> {
    return this.api.post(
      `/organization-applications/${applicationId}/resubmit`,
      {}
    );
  }

  getApplicationById(
    applicationId: number | string
  ): Observable<OrganizationApplicationDetail> {
    return this.api
      .get<OrganizationApplicationDetailResponse>(
        `/admin/organization-applications/${applicationId}`
      )
      .pipe(
        map((res) => {
          const detail = res?.data;
          return {
            ...detail,
            verification_status: detail?.verification_status ?? detail?.status ?? '',
            documents: detail?.documents ?? [],
            status_history: detail?.status_history ?? [],
            reviews: detail?.reviews ?? [],
          };
        })
      );
  }

  submitDecision(
    applicationId: number | string,
    payload: DecisionRequestPayload
  ): Observable<DecisionResponsePayload> {
    const normalizedPayload: DecisionRequestPayload = {
      decision: payload.decision,
      review_note: payload.review_note.trim(),
    };

    return this.api.post<DecisionResponsePayload>(
      `/admin/organization-applications/${applicationId}/decision`,
      normalizedPayload
    );
  }
}
