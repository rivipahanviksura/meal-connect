import { CommonModule } from '@angular/common';
import { Component, inject, Input, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import { HttpErrorResponse } from '@angular/common/http';
import {
  AdminDecisionValue,
  DecisionAction,
  OrganizationApplicationDetail,
} from '../../core/models/navigation-account';
import { OrganizationVerificationService } from '../../core/services/organization-verification.service';

const MIN_REVIEW_NOTE_LENGTH = 10;

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
  protected reviewNote = signal('');
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
      next: (detail) => {
        this.application.set(detail);
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

  onReviewNoteChange(val: string): void {
    this.reviewNote.set(val);
    this.resetConfirmation();
  }

  protected mapActionToDecision(action: DecisionAction): AdminDecisionValue {
    if (action === 'approve') return 'approved';
    if (action === 'reject') return 'rejected';
    return 'request_corrections';
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

    const trimmedNote = this.reviewNote().trim();
    if (trimmedNote.length < MIN_REVIEW_NOTE_LENGTH) {
      this.errorMessage.set(
        `Please enter a review note of at least ${MIN_REVIEW_NOTE_LENGTH} characters for all decisions.`
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

    const trimmedNote = this.reviewNote().trim();
    if (trimmedNote.length < MIN_REVIEW_NOTE_LENGTH) {
      this.errorMessage.set(
        `Please enter a review note of at least ${MIN_REVIEW_NOTE_LENGTH} characters for all decisions.`
      );
      this.confirmRequested.set(false);
      return;
    }

    this.submitting.set(true);
    this.errorMessage.set(null);
    this.successMessage.set(null);
    this.fieldErrors.set({});

    const decision = this.mapActionToDecision(this.selectedAction());
    const payload = {
      decision,
      review_note: trimmedNote,
    };

    this.verificationService.submitDecision(this.resolvedId, payload).subscribe({
      next: (decisionRes) => {
        this.submitting.set(false);
        this.confirmRequested.set(false);
        this.reviewNote.set('');

        const updatedStatus = decisionRes?.data?.verification_status ?? decision;
        this.successMessage.set(
          decisionRes?.message ||
            `Decision "${decision}" submitted successfully (Status: ${updatedStatus}).`
        );
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