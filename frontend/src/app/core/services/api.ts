import {inject, Injectable} from '@angular/core';
import {HttpClient} from '@angular/common/http';
import {Observable} from 'rxjs';

@Injectable({
  providedIn: 'root',
})
export class Api {
  private readonly http = inject(HttpClient);

  private readonly baseUrl = '/api/v1';

  get<T>(
    endpoint: string,
    options?: { headers?: Record<string, string> },
  ): Observable<T> {
    return this.http.get<T>(this.url(endpoint), options);
  }

  post<T>(
    endpoint: string,
    body: unknown,
    options?: { headers?: Record<string, string> },
  ): Observable<T> {
    return this.http.post<T>(this.url(endpoint), body, options);
  }

  put<T>(endpoint: string, body: unknown): Observable<T> {
    return this.http.put<T>(this.url(endpoint), body);
  }

  delete<T>(endpoint: string): Observable<T> {
    return this.http.delete<T>(this.url(endpoint));
  }

  private url(endpoint: string): string {
    return `${this.baseUrl}/${endpoint.replace(/^\/+/, '')}`;
  }
}
