import { CommonModule } from '@angular/common';
import { Component, inject, Input, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
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

    this.verificationService.getApplicationById(this.resolvedId).subscribe({
      next: (data) => {
        this.application.set(data);
        this.loading.set(false);
      },
      error: (err) => {
        this.errorMessage.set(
          err?.error?.message || err?.message || 'Unable to load application details.'
        );
        this.loading.set(false);
      },
    });
  }

  onSelectAction(action: DecisionAction): void {
    this.selectedAction.set(action);
    this.confirmRequested.set(false);
    this.errorMessage.set(null);
    this.successMessage.set(null);
  }

  requestConfirmation(): void {
    this.errorMessage.set(null);
    this.successMessage.set(null);

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
      error: (err) => {
        this.submitting.set(false);
        this.confirmRequested.set(false);
        this.errorMessage.set(
          err?.error?.message || err?.message || 'Failed to submit verification decision.'
        );
      },
    });
  }
}
