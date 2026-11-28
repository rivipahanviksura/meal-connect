import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Observable, throwError } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { DonationDetail } from '../models/donation-detail.model';

export interface ApiErrorState {
  status: number;
  title: string;
  message: string;
}

@Injectable({ providedIn: 'root' })
export class DonationDetailApi {
  private http = inject(HttpClient);
  private readonly apiUrl = '/api/v1/donations';

  getDonationById(id: string): Observable<DonationDetail> {
    return this.http.get<DonationDetail>(`${this.apiUrl}/${id}`).pipe(
      catchError((error: HttpErrorResponse) => this.handleError(error))
    );
  }

  claimDonation(id: string, notes: string): Observable<{ claimReference: string }> {
    return this.http.post<{ claimReference: string }>(`${this.apiUrl}/${id}/claim`, { notes }).pipe(
      catchError((error: HttpErrorResponse) => this.handleError(error))
    );
  }

  private handleError(error: HttpErrorResponse): Observable<never> {
    let errorState: ApiErrorState = {
      status: error.status || 500,
      title: 'Unexpected Error',
      message: 'Something went wrong while loading the donation details.'
    };

    if (error.status === 401) {
      errorState = {
        status: 401,
        title: 'Authentication Required',
        message: 'Your session has expired. Please sign in again to view this listing.'
      };
    } else if (error.status === 403) {
      errorState = {
        status: 403,
        title: 'Access Restricted',
        message: 'Your organization does not have permission to view this donation record.'
      };
    } else if (error.status === 404 || error.status === 410) {
      errorState = {
        status: error.status,
        title: 'Listing Unavailable',
        message: 'This donation has either been removed, expired, or already claimed.'
      };
    }

    return throwError(() => errorState);
  }
}
