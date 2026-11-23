import { CommonModule } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ApplicationSummaryItem } from '../../core/models/navigation-account';
import { OrganizationVerificationService } from '../../core/services/organization-verification.service';

@Component({
  selector: 'app-organization-feedback',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './organization-feedback.html',
})
export class OrganizationFeedback implements OnInit {
  private readonly verificationService = inject(OrganizationVerificationService);

  protected readonly loading = signal(true);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly submittingResubmit = signal(false);
  protected readonly feedbackMessage = signal<string | null>(null);
  protected readonly application = signal<ApplicationSummaryItem | null>(null);

  ngOnInit(): void {
    this.loadStatus();
  }

  loadStatus(): void {
    this.loading.set(true);
    this.errorMessage.set(null);

    this.verificationService.getMyApplications().subscribe({
      next: (res) => {
        this.application.set(res.data?.[0] ?? null);
        this.loading.set(false);
      },
      error: (err) => {
        this.errorMessage.set(
          err?.error?.message || err?.message || 'Unable to load verification status.'
        );
        this.loading.set(false);
      },
    });
  }

  onResubmit(): void {
    const app = this.application();
    if (!app || this.submittingResubmit()) {
      return;
    }

    this.submittingResubmit.set(true);
    this.feedbackMessage.set(null);
    this.errorMessage.set(null);

    this.verificationService.resubmitApplication(app.application_id).subscribe({
      next: () => {
        this.submittingResubmit.set(false);
        this.feedbackMessage.set('Application resubmitted for verification.');
        this.loadStatus();
      },
      error: (err) => {
        this.submittingResubmit.set(false);
        this.errorMessage.set(
          err?.error?.message || err?.message || 'Unable to resubmit application.'
        );
      },
    });
  }
}
