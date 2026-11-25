import { CommonModule } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HttpErrorResponse } from '@angular/common/http';
import { RouterLink } from '@angular/router';
import { finalize, of, switchMap } from 'rxjs';
import { ApplicationSummaryItem } from '../../core/models/navigation-account';
import { OrganizationVerificationService } from '../../core/services/organization-verification.service';

@Component({
  selector: 'app-organization-feedback',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './organization-feedback.html',
})
export class OrganizationFeedback implements OnInit {
  private readonly verificationService = inject(OrganizationVerificationService);

  protected readonly loading = signal(true);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly fieldErrors = signal<Record<string, string[]>>({});
  protected readonly submittingResubmit = signal(false);
  protected readonly feedbackMessage = signal<string | null>(null);
  protected readonly application = signal<ApplicationSummaryItem | null>(null);

  protected readonly correctionNote = signal('');
  protected readonly documentType = signal('supporting_document');
  protected readonly selectedFile = signal<File | null>(null);
  protected readonly selectedDocumentName = signal('');

  ngOnInit(): void {
    this.loadStatus();
  }

  loadStatus(): void {
    this.loading.set(true);
    this.errorMessage.set(null);
    this.fieldErrors.set({});

    this.verificationService.getMyApplications().subscribe({
      next: (res) => {
        this.application.set(res.data?.[0] ?? null);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.applyApiError(err, 'Unable to load verification status.');
        this.loading.set(false);
      },
    });
  }

  onResubmit(): void {
    const app = this.application();
    if (!app || this.submittingResubmit()) {
      return;
    }

    const file = this.selectedFile();
    const docType = this.documentType().trim() || 'supporting_document';
    const note = this.correctionNote().trim();

    this.submittingResubmit.set(true);
    this.feedbackMessage.set(null);
    this.errorMessage.set(null);
    this.fieldErrors.set({});

    const uploadStep$ = file
      ? this.verificationService.uploadDocument(app.application_id, file, docType)
      : of(null);

    uploadStep$
      .pipe(
        switchMap(() =>
          this.verificationService.resubmitApplication(app.application_id, note)
        ),
        finalize(() => this.submittingResubmit.set(false))
      )
      .subscribe({
        next: () => {
          this.correctionNote.set('');
          this.selectedFile.set(null);
          this.selectedDocumentName.set('');
          this.feedbackMessage.set(
            file
              ? 'Document uploaded and application resubmitted for verification.'
              : 'Application resubmitted for verification.'
          );
          this.loadStatus();
        },
        error: (err: unknown) => {
          this.applyApiError(
            err,
            file
              ? 'Failed to upload document or resubmit application.'
              : 'Unable to resubmit application.'
          );
        },
      });
  }

  protected onDocumentFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement | null;
    const file = input?.files?.[0] ?? null;
    this.selectedFile.set(file);
    this.selectedDocumentName.set(file ? file.name : '');
  }

  protected canResubmit(status: string | undefined): boolean {
    return (
      status === 'rejected' ||
      status === 'request_corrections' ||
      status === 'corrections_requested' ||
      status === 'needs_correction' ||
      status === 'correction_requested'
    );
  }

  private applyApiError(err: unknown, fallback: string): void {
    const parsed = this.extractApiError(err, fallback);
    this.errorMessage.set(parsed.message);
    this.fieldErrors.set(parsed.fields);
  }

  private extractApiError(
    err: unknown,
    fallback: string
  ): { message: string; fields: Record<string, string[]> } {
    const httpErr = err instanceof HttpErrorResponse ? err : null;
    const status = httpErr?.status ?? (err as { status?: number } | null)?.status;
    const payload =
      httpErr?.error ?? (err as { error?: unknown } | null)?.error ?? err;

    const errObj =
      payload && typeof payload === 'object'
        ? ((payload as { error?: Record<string, unknown> }).error ??
            (payload as Record<string, unknown>))
        : null;

    const code = typeof errObj?.['code'] === 'string' ? errObj['code'] : undefined;
    const rawMsg =
      typeof errObj?.['message'] === 'string' && errObj['message'].trim().length > 0
        ? errObj['message'].trim()
        : undefined;

    const fields: Record<string, string[]> = {};
    const rawFields = errObj?.['fields'];
    if (rawFields && typeof rawFields === 'object') {
      for (const [key, val] of Object.entries(rawFields as Record<string, unknown>)) {
        if (Array.isArray(val)) {
          fields[key] = val.map((item) => String(item));
        } else if (typeof val === 'string') {
          fields[key] = [val];
        }
      }
    }

    let message = rawMsg || fallback;

    switch (status) {
      case 401:
        message = rawMsg || 'Your session has expired. Please sign in again.';
        break;
      case 403:
        message = rawMsg || 'You do not have permission to view or update this application.';
        break;
      case 404:
        message = rawMsg || 'Organization application was not found.';
        break;
      case 409:
        message =
          rawMsg ||
          'Application state has changed. Refresh the status before resubmitting.';
        break;
      case 422:
        message = rawMsg || 'Please review and fix the required application corrections.';
        break;
    }

    if (code && !message.includes(code)) {
      message = `${message} (${code})`;
    }

    return { message, fields };
  }
}