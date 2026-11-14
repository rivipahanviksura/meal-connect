import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import {
  FormControl,
  FormGroup,
  ReactiveFormsModule,
  Validators,
} from '@angular/forms';
import { HttpErrorResponse } from '@angular/common/http';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { catchError, EMPTY, finalize, map, of, switchMap } from 'rxjs';

import { RegistrationApi } from '../services/registration-api';

@Component({
  selector: 'app-login',
  imports: [ReactiveFormsModule],
  templateUrl: './login.html',
  styleUrl: './login.scss',
})
export class Login {
  readonly form = new FormGroup({
    email: new FormControl('', {
      nonNullable: true,
      validators: [Validators.required, Validators.email],
    }),
    password: new FormControl('', {
      nonNullable: true,
      validators: [Validators.required],
    }),
  });
  private readonly registrationApi = inject(RegistrationApi);
  private readonly destroyRef = inject(DestroyRef);

  readonly isSubmitting = signal(false);
  readonly loginError = signal<string | null>(null);
  readonly loginMessage = signal<string | null>(null);

  private readonly rejectedApplication = signal<{
    id: number;
    accessToken: string;
  } | null>(null);

  readonly canResubmit = computed(() => this.rejectedApplication() !== null);
  readonly isResubmitting = signal(false);
  readonly resubmitError = signal<string | null>(null);

  readonly isUploadingCorrection = signal(false);
  readonly correctionError = signal<string | null>(null);
  readonly correctionMessage = signal<string | null>(null);

  submit(): void {
    if (this.isSubmitting() || this.isResubmitting() || this.isUploadingCorrection()) {
      return;
    }

    this.rejectedApplication.set(null);
    this.resubmitError.set(null);
    this.correctionError.set(null);
    this.correctionMessage.set(null);
    this.loginError.set(null);
    this.loginMessage.set(null);
    this.form.markAllAsTouched();

    if (this.form.invalid) {
      return;
    }

    const { email, password } = this.form.getRawValue();

    this.isSubmitting.set(true);

    this.registrationApi.login({
      email: email.trim().toLowerCase(),
      password,
    }).pipe(
      switchMap(({ data }) => {
        this.form.controls.password.reset();

        if (data.user.role !== 'business_staff' && data.user.role !== 'ngo_staff') {
          return of('Credentials verified.');
        }

        return this.registrationApi.getMyApplications(data.access_token).pipe(
          map(({ data: applications }) => {
            const application = applications[0];
            if (
              application && typeof application === 'object' &&
              'status' in application && application.status === 'rejected' &&
              'application_id' in application &&
              typeof application.application_id === 'number' &&
              Number.isSafeInteger(application.application_id) &&
              application.application_id > 0 && data.access_token
            ) {
              this.rejectedApplication.set({
                id: application.application_id,
                accessToken: data.access_token,
              });
            }

            return this.getApplicationStatusMessage(applications);
          }),
          catchError(() => {
            this.loginError.set(
              'You signed in, but we could not load your application status. Please try again.',
            );
            return EMPTY;
          }),
        );
      }),
      takeUntilDestroyed(this.destroyRef),
      finalize(() => this.isSubmitting.set(false)),
    ).subscribe(
      {next: (message) => this.loginMessage.set(message),
        error: (response: unknown) => {
          const apiMessage = response instanceof HttpErrorResponse
            ? response.error?.error?.message
            : undefined;

          const fallback = response instanceof HttpErrorResponse && response.status === 401
            ? 'Invalid email or password.'
            : 'We could not complete login. Please try again.';

          this.loginError.set(
            typeof apiMessage === 'string' && apiMessage.trim()
              ? apiMessage.trim()
              : fallback,
          );
          if (response instanceof HttpErrorResponse && response.status === 422) {
            const fields: unknown = response.error?.error?.fields;

            if (Array.isArray(fields)) {
              for (const field of fields) {
                if (
                  (field?.field === 'email' || field?.field === 'password') &&
                  typeof field.message === 'string' &&
                  field.message.trim()
                ) {
                  const control = this.form.get(field.field);

                  if (control) {
                    control.setErrors({ ...control.errors, server: field.message.trim() });
                  }
                }
              }
            }
          }
        },
      });
  }
  uploadCorrection(input: HTMLInputElement, documentType: string): void {
    const application = this.rejectedApplication();
    if (!application || this.isSubmitting() || this.isResubmitting() || this.isUploadingCorrection()) {
      return;
    }

    this.correctionError.set(null);
    this.correctionMessage.set(null);
    const file = input.files?.item(0);
    if (!file || !documentType) {
      this.correctionError.set('Choose a document type and a file.');
      return;
    }

    const allowedExtensions = new Map([
      ['application/pdf', ['.pdf']],
      ['image/jpeg', ['.jpg', '.jpeg']],
      ['image/png', ['.png']],
    ]);
    const name = file.name.toLowerCase();
    if (!allowedExtensions.get(file.type)?.some((extension) => name.endsWith(extension))) {
      this.correctionError.set('Choose a PDF, JPG or PNG file.');
      return;
    }

    if (file.size === 0 || file.size > 5 * 1024 * 1024) {
      this.correctionError.set('Choose a non-empty file no larger than 5 MiB.');
      return;
    }

    this.isUploadingCorrection.set(true);
    this.registrationApi.uploadVerificationDocument(
      application.id, application.accessToken, documentType, file,
    ).pipe(
      takeUntilDestroyed(this.destroyRef),
      finalize(() => this.isUploadingCorrection.set(false)),
    ).subscribe({
      next: () => {
        input.value = '';
        this.correctionMessage.set('Corrected document uploaded.');
      },
      error: (response: unknown) => {
        if (response instanceof HttpErrorResponse && response.status === 401) {
          this.rejectedApplication.set(null);
          this.correctionError.set('Please sign in again to upload your correction.');
          return;
        }

        const message = response instanceof HttpErrorResponse
          ? response.error?.error?.message
          : undefined;
        this.correctionError.set(
          typeof message === 'string' && message.trim()
            ? message.trim()
            : 'We could not upload your corrected document. Please try again.',
        );
      },
    });
  }

  resubmit(): void {
    const application = this.rejectedApplication();
    if (!application || this.isSubmitting() || this.isResubmitting() || this.isUploadingCorrection()) {
      return;
    }

    this.resubmitError.set(null);
    this.isResubmitting.set(true);

    this.registrationApi.resubmitApplication(application.id, application.accessToken).pipe(
      takeUntilDestroyed(this.destroyRef),
      finalize(() => this.isResubmitting.set(false)),
    ).subscribe({
      next: (response) => {
        if (response?.data?.status !== 'pending_verification') {
          this.resubmitError.set('We could not confirm resubmission. Sign in again to check your application status.');
          this.rejectedApplication.set(null);
          return;
        }

        this.rejectedApplication.set(null);
        this.correctionError.set(null);
        this.correctionMessage.set(null);
        this.loginMessage.set(this.getApplicationStatusMessage([response.data]));
      },
      error: (response: unknown) => {
        if (response instanceof HttpErrorResponse && response.status === 401) {
          this.rejectedApplication.set(null);
          this.resubmitError.set('Please sign in again to resubmit your application.');
          return;
        }

        const message = response instanceof HttpErrorResponse
          ? response.error?.error?.message
          : undefined;

        this.resubmitError.set(
          typeof message === 'string' && message.trim()
            ? message.trim()
            : 'We could not resubmit your application. Please try again.',
        );
      },
    });
  }

  private getApplicationStatusMessage(applications: unknown[]): string {
    if (applications.length === 0) {
      return 'You do not have an organization application yet.';
    }

    const application = applications[0];
    const status = application && typeof application === 'object'
    && 'status' in application
      ? application.status
      : undefined;

    switch (status) {
      case 'draft':
        return 'Your application is saved as a draft.';
      case 'pending_verification':
        return 'Pending Verification. Your application is awaiting admin review.';
      case 'verified':
        return 'Your organization application has been verified.';
      case 'rejected': {
        const reviewNote =
          application &&
          typeof application === 'object' &&
          'review_note' in application &&
          typeof application.review_note === 'string'
            ? application.review_note.trim()
            : '';

        const instructions =
          'Review the feedback and prepare the requested corrections before resubmitting.';

        return reviewNote
          ? `Your organization application was rejected. ${reviewNote} ${instructions}`
          : 'Your organization application was rejected. No review note is available.';
      }
      case 'suspended':
        return 'Your organization verification has been suspended.';
      default:
        return 'Your application status could not be determined.';
    }
  }
}
