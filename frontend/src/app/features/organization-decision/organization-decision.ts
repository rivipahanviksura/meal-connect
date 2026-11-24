import { CommonModule } from '@angular/common';
import { Component, inject, Input, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import { HttpErrorResponse } from '@angular/common/http';
import {
  DecisionAction,
  OrganizationApplicationDetail,
} from '../../core/models/navigation-account';
import { OrganizationVerificationService } from '../../core/services/organization-verification.service';

@Component({
  selector: 'app-organization-decision',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './organization-decision.html',
})
export class OrganizationDecision implements OnInit {
  private readonly verificationService = inject(OrganizationVerificationService);
  private readonly route = inject(ActivatedRoute);

  @Input() applicationId?: number | string;

  protected readonly loading = signal(true);
  protected readonly submitting = signal(false);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly fieldErrors = signal<Record<string, string[]>>({});
  protected readonly successMessage = signal<string | null>(null);
  protected readonly application = signal<OrganizationApplicationDetail | null>(null);

  protected selectedAction = signal<DecisionAction>('approve');
  protected reason = signal('');
  protected internalComment = signal('');
  protected confirmRequested = signal(false);

  private resolvedId: number | string | null = null;

  ngOnInit(): void {
    this.resolvedId =
      this.applicationId ?? this.route.snapshot.paramMap.get('id');
    this.loadApplication();
  }

  loadApplication(): void {
    if (!this.resolvedId) {
      this.errorMessage.set('Application ID is missing.');
      this.loading.set(false);
      return;
    }

    this.loading.set(true);
    this.errorMessage.set(null);
    this.fieldErrors.set({});

    this.verificationService.getApplicationById(this.resolvedId).subscribe({
      next: (res) => {
        // Backend (MEAL-89) returns wrapped in 'data' envelope
        const data = (res as any)?.data ?? res;
        this.application.set(data);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.applyApiError(err, 'Unable to load application details.');
        this.loading.set(false);
      },
    });
  }

  onSelectAction(action: DecisionAction): void {
    this.selectedAction.set(action);
    this.resetConfirmation();
  }

  onReasonChange(val: string): void {
    this.reason.set(val);
    this.resetConfirmation();
  }

  onInternalCommentChange(val: string): void {
    this.internalComment.set(val);
    this.resetConfirmation();
  }

  private resetConfirmation(): void {
    if (this.confirmRequested()) {
      this.confirmRequested.set(false);
    }
    this.errorMessage.set(null);
    this.successMessage.set(null);
    this.fieldErrors.set({});
  }

  requestConfirmation(): void {
    this.errorMessage.set(null);
    this.successMessage.set(null);
    this.fieldErrors.set({});

    const action = this.selectedAction();
    const trimmedReason = this.reason().trim();

    if ((action === 'reject' || action === 'request_corrections') && trimmedReason.length < 5) {
      this.errorMessage.set(
        'Please enter a meaningful reason (at least 5 characters) for rejection or corrections.'
      );
      return;
    }

    this.confirmRequested.set(true);
  }

  cancelConfirmation(): void {
    this.confirmRequested.set(false);
  }

  confirmSubmitDecision(): void {
    if (this.submitting() || !this.resolvedId) {
      return;
    }

    this.submitting.set(true);
    this.errorMessage.set(null);
    this.successMessage.set(null);
    this.fieldErrors.set({});

    const action = this.selectedAction();
    const payload = {
      action,
      reason: this.reason().trim() || undefined,
      internal_comment: this.internalComment().trim() || undefined,
    };

    this.verificationService.submitDecision(this.resolvedId, payload).subscribe({
      next: () => {
        this.submitting.set(false);
        this.confirmRequested.set(false);
        this.reason.set('');
        this.internalComment.set('');
        this.successMessage.set(`Decision "${action}" submitted successfully.`);
        this.loadApplication();
      },
      error: (err: unknown) => {
        this.submitting.set(false);
        this.confirmRequested.set(false);
        this.applyApiError(err, 'Failed to submit verification decision.');
      },
    });
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
        message = rawMsg || 'You do not have permission to perform admin verification decisions.';
        break;
      case 404:
        message = rawMsg || 'Organization application was not found.';
        break;
      case 409:
        message = rawMsg || 'Decision conflict: The application state has changed.';
        break;
      case 422:
        message = rawMsg || 'Invalid decision data. Please check the fields.';
        break;
    }

    if (code && !message.includes(code)) {
      message = `${message} (${code})`;
    }

    return { message, fields };
  }
}
