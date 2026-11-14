
import {Component, computed, signal, DestroyRef, inject} from '@angular/core';
import {
  AbstractControl,
  FormControl,
  FormGroup,
  ReactiveFormsModule,
  ValidationErrors,
  Validators
} from '@angular/forms';

import {
  RegisterAccountRequest,
  ApiFieldError,
  mapRegistrationFieldError,
  RegistrationApi,
  type CreateBusinessApplicationRequest,
  type CreateNgoApplicationRequest
} from '../services/registration-api';

import { HttpErrorResponse } from '@angular/common/http';
import {takeUntilDestroyed} from '@angular/core/rxjs-interop';
import { concatMap, finalize, from, last, of, startWith, tap } from 'rxjs';


export type AccountType = 'business' | 'ngo';

export type VerificationDocumentType =
  | 'registration_certificate'
  | 'representative_authorization'
  | 'supporting_document';

export interface SelectedVerificationDocument {
  type: VerificationDocumentType;
  file: File;
}


function passwordsMatch(
  control: AbstractControl
): ValidationErrors | null {
  const password = control.get('password')?.value;
  const confirmPassword = control.get('confirmPassword')?.value;

  if (!password || !confirmPassword) {
    return null;
  }

  return password === confirmPassword
    ? null
    : { passwordMismatch: true };
}

function registrationDateValidator(
  control: AbstractControl
): ValidationErrors | null {
  const value = control.value as string;

  if (!value) {
    return null;
  }

  const date = new Date(`${value}T00:00:00`);

  if (Number.isNaN(date.getTime())) {
    return { invalidDate: true };
  }

  const today = new Date();
  today.setHours(0, 0, 0, 0);

  return date > today
    ? { futureDate: true }
    : null;
}

const requiredText = () =>
  new FormControl('', {
    nonNullable: true,
    validators: [
      Validators.required,
      Validators.maxLength(255)
    ]
  });

const optionalText = () =>
  new FormControl('', {
    nonNullable: true,
    validators: [Validators.maxLength(255)]
  });

@Component({
  selector: 'app-register',
  standalone: true,
  imports: [ReactiveFormsModule],
  templateUrl: './register.html',
  styleUrl: './register.scss'
})
export class Register {
  readonly selectedAccountType =
    signal<AccountType | null>(null);

  // 0: Account Type
  // 1: Account Details
  // 2: Organization Details
  readonly currentStep = signal(0);
  readonly registrationError = signal<string | null>(null);

  readonly accountForm = new FormGroup(
    {
      firstName: new FormControl('', {
        nonNullable: true,
        validators: [
          Validators.required,
          Validators.minLength(2),
          Validators.maxLength(100)
        ]
      }),

      lastName: new FormControl('', {
        nonNullable: true,
        validators: [
          Validators.required,
          Validators.minLength(2),
          Validators.maxLength(100)
        ]
      }),

      email: new FormControl('', {
        nonNullable: true,
        validators: [
          Validators.required,
          Validators.email
        ]
      }),

      password: new FormControl('', {
        nonNullable: true,
        validators: [
          Validators.required,
          Validators.minLength(8)
        ]
      }),

      confirmPassword: new FormControl('', {
        nonNullable: true,
        validators: [Validators.required]
      }),

      phone: optionalText()
    },
    { validators: passwordsMatch }
  );

  readonly businessForm = new FormGroup({
    businessName: requiredText(),
    registrationNumber: requiredText(),

    businessType: new FormControl('', {
      nonNullable: true,
      validators: [Validators.required]
    }),

    registeredAddress: requiredText(),
    city: requiredText(),
    pickupLocation: requiredText(),

    contactEmail: new FormControl('', {
      nonNullable: true,
      validators: [
        Validators.required,
        Validators.email
      ]
    }),

    contactPhone: requiredText(),
    representativeDesignation: requiredText()
  });

  readonly ngoForm = new FormGroup({
    ngoName: requiredText(),
    registrationNumber: requiredText(),
    registrationAuthority: requiredText(),

    registrationDate: new FormControl('', {
      nonNullable: true,
      validators: [
        Validators.required,
        registrationDateValidator
      ]
    }),

    registeredAddress: requiredText(),
    city: requiredText(),
    operatingArea: requiredText(),

    contactEmail: new FormControl('', {
      nonNullable: true,
      validators: [
        Validators.required,
        Validators.email
      ]
    }),

    contactPhone: requiredText(),
    representativeDesignation: requiredText(),
    distributionArea: requiredText(),
    operationalCapability: requiredText()
  });

  selectAccountType(type: AccountType): void {
    this.selectedAccountType.set(type);
  }

  continueToAccountDetails(): void {
    if (!this.selectedAccountType()) {
      return;
    }

    this.currentStep.set(1);
  }

  validateAccountDetails(): boolean {
    this.accountForm.markAllAsTouched();

    if (this.accountForm.invalid) {
      return false;
    }

    this.currentStep.set(2);
    return true;
  }

  validateOrganizationDetails(): boolean {
    const type = this.selectedAccountType();

    if (!type) {
      return false;
    }

    const form =
      type === 'business'
        ? this.businessForm
        : this.ngoForm;

    form.markAllAsTouched();

    if (form.invalid) {
      return false;
    }

    // Proceed only after successful validation.
    this.currentStep.set(3);

    return true;
  }


  backToAccountDetails(): void {
    this.currentStep.set(1);
  }

// Provisional limits from the API contract.
// Confirm with the backend team before final integration.
  readonly maxDocumentSize = 5 * 1024 * 1024;
  readonly maxDocumentCount = 3;

  readonly selectedDocuments =
    signal<SelectedVerificationDocument[]>([]);

  readonly documentError = signal<string | null>(null);

  onDocumentSelected(
    event: Event,
    documentType: VerificationDocumentType
  ): void {
    if (this.isSubmittingApplication() || this.isDocumentUploaded(documentType)) {
      return;
    }
    const input = event.target as HTMLInputElement;
    const file = input.files?.item(0);

    this.documentError.set(null);

    if (!file) {
      return;
    }

    const allowedTypes = new Map([
      ['application/pdf', '.pdf'],
      ['image/jpeg', '.jpg'],
      ['image/png', '.png']
    ]);

    const extension = file.name
      .slice(file.name.lastIndexOf('.'))
      .toLowerCase();

    const expectedExtensions = new Map([
      ['application/pdf', ['.pdf']],
      ['image/jpeg', ['.jpg', '.jpeg']],
      ['image/png', ['.png']]
    ]);

    const validMimeType = allowedTypes.has(file.type);

    const validExtension =
      expectedExtensions.get(file.type)?.includes(extension) ?? false;

    if (!validMimeType || !validExtension) {
      this.documentError.set(
        'Only PDF, JPG and PNG documents are allowed.'
      );
      input.value = '';
      return;
    }

    if (file.size === 0 || file.size > this.maxDocumentSize) {
      this.documentError.set(
        'Each document must be larger than 0 bytes and no more than 5 MiB.'
      );
      input.value = '';
      return;
    }

    const existingDocuments = this.selectedDocuments()
      .filter(document => document.type !== documentType);

    if (existingDocuments.length >= this.maxDocumentCount) {
      this.documentError.set(
        'You can select a maximum of 3 documents.'
      );
      input.value = '';
      return;
    }

    this.selectedDocuments.set([
      ...existingDocuments,
      { type: documentType, file }
    ]);

    // Clear the native input so the same file can be selected again.
    input.value = '';
  }

  removeDocument(documentType: VerificationDocumentType): void {
    if (this.isSubmittingApplication() || this.isDocumentUploaded(documentType)) {
      return;
    }
    this.selectedDocuments.update(documents =>
      documents.filter(document => document.type !== documentType)
    );

    this.documentError.set(null);
  }

  backToOrganizationDetails(): void {
    this.currentStep.set(2);
  }

  hasRequiredDocuments(): boolean {
    return this.selectedDocuments().some(
      document => document.type === 'registration_certificate'
    );
  }

  continueToReview(): void {
    this.documentError.set(null);

    if (!this.hasRequiredDocuments()) {
      this.documentError.set(
        'Please select your organization registration certificate before continuing.'
      );
      return;
    }

    this.currentStep.set(4);
  }

  backToDocuments(): void {
    this.currentStep.set(3);
  }

  readonly informationDeclarationAccepted = signal(false);

  readonly verificationDeclarationAccepted = signal(false);

  readonly declarationsAccepted = computed(() =>
    this.informationDeclarationAccepted() &&
    this.verificationDeclarationAccepted()
  );

  setInformationDeclaration(checked: boolean): void {
    this.informationDeclarationAccepted.set(checked);
  }

  setVerificationDeclaration(checked: boolean): void {
    this.verificationDeclarationAccepted.set(checked);
  }
  buildAccountRegistrationRequest(): RegisterAccountRequest | null {
    const accountType = this.selectedAccountType();

    if (!accountType || this.accountForm.invalid) {
      return null;
    }

    const form = this.accountForm.getRawValue();

    return {
      first_name: form.firstName.trim(),
      last_name: form.lastName.trim(),
      email: form.email.trim().toLowerCase(),
      password: form.password,
      phone: form.phone.trim() || null,
      account_type: accountType
    };
  }
  buildNgoApplicationRequest(): CreateNgoApplicationRequest | null {
    if (this.selectedAccountType() !== 'ngo' || this.ngoForm.invalid) {
      return null;
    }

    const organization = this.ngoForm.getRawValue();
    const account = this.accountForm.getRawValue();

    const name = organization.ngoName.trim();
    const addressLine = organization.registeredAddress.trim();
    const city = organization.city.trim();
    const representativeName = `${account.firstName.trim()} ${account.lastName.trim()}`.trim();

    if (!name || !addressLine || !city || !representativeName) {
      return null;
    }

    return {
      organization_type: 'ngo',
      name,
      registration_number: organization.registrationNumber.trim() || undefined,
      contact_email: organization.contactEmail.trim().toLowerCase(),
      contact_phone: organization.contactPhone.trim() || undefined,
      address_line: addressLine,
      city,
      representative_name: representativeName,
    };
  }
  buildBusinessApplicationRequest(): CreateBusinessApplicationRequest | null {
    if (this.selectedAccountType() !== 'business' || this.businessForm.invalid) {
      return null;
    }

    const organization = this.businessForm.getRawValue();
    const account = this.accountForm.getRawValue();
    const subtype = organization.businessType;

    if (subtype !== 'restaurant' && subtype !== 'bakery') {
      return null;
    }

    const name = organization.businessName.trim();
    const addressLine = organization.registeredAddress.trim();
    const city = organization.city.trim();
    const representativeName = `${account.firstName.trim()} ${account.lastName.trim()}`.trim();

    if (!name || !addressLine || !city || !representativeName) {
      return null;
    }

    return {
      organization_type: 'business',
      business_subtype: subtype,
      name,
      registration_number: organization.registrationNumber.trim() || undefined,
      contact_email: organization.contactEmail.trim().toLowerCase(),
      contact_phone: organization.contactPhone.trim() || undefined,
      address_line: addressLine,
      city,
      representative_name: representativeName,
    };
  }

  handleAccountRegistrationError(response: unknown): void {
    const error = response instanceof HttpErrorResponse
      ? response.error?.error
      : undefined;

    const message = typeof error?.message === 'string'
      ? error.message.trim()
      : '';

    this.registrationError.set(
      message || 'We could not create your account. Please try again.'
    );

    if (Array.isArray(error?.fields)) {
      const fields = error.fields.filter(
        (field: Partial<ApiFieldError> | null): field is ApiFieldError =>
          typeof field?.field === 'string' &&
          typeof field?.message === 'string' &&
          typeof field?.code === 'string'
      );

      this.applyAccountServerErrors(fields);
    }

    this.currentStep.set(1);
  }

  private readonly accountServerErrors = new WeakMap<
    AbstractControl,
    { value: string; message: string }
  >();

  private readonly validateAccountServerError = (
    control: AbstractControl
  ): ValidationErrors | null => {
    const error = this.accountServerErrors.get(control);

    if (!error) {
      return null;
    }

    if (control.value !== error.value) {
      this.accountServerErrors.delete(control);
      return null;
    }

    return { server: error.message };
  };

  applyAccountServerErrors(fields: ApiFieldError[]): void {
    for (const fieldError of fields) {
      const controlName = mapRegistrationFieldError(fieldError.field);

      if (!controlName) {
        continue;
      }

      const control = this.accountForm.controls[controlName];
      this.accountServerErrors.set(control, {
        value: control.value,
        message: fieldError.message
      });

      control.addValidators(this.validateAccountServerError);
      control.markAsTouched();
      control.updateValueAndValidity();
    }
  }
  private readonly registrationApi = inject(RegistrationApi);
  private readonly destroyRef = inject(DestroyRef);

  readonly isRegisteringAccount = signal(false);
  readonly accountCreated = signal(false);

  registerAccount(): void {
    if (this.isRegisteringAccount() || this.accountCreated()) {
      return;
    }

    this.accountForm.markAllAsTouched();
    const request = this.buildAccountRegistrationRequest();

    if (!request) {
      this.currentStep.set(1);
      return;
    }

    this.registrationError.set(null);
    this.isRegisteringAccount.set(true);

    this.registrationApi.registerAccount(request)
      .pipe(
        takeUntilDestroyed(this.destroyRef),
        finalize(() => this.isRegisteringAccount.set(false)),
      )
      .subscribe({
        next: () => this.accountCreated.set(true),
        error: (response: unknown) => this.handleAccountRegistrationError(response),
      });
  }
  readonly isSubmittingApplication = signal(false);
  readonly applicationSubmitted = signal(false);
  readonly applicationSubmitError = signal<string | null>(null);
  readonly draftApplicationId = signal<number | null>(null);

  private readonly uploadedDocuments = new Set<SelectedVerificationDocument>();

  isDocumentUploaded(documentType: VerificationDocumentType): boolean {
    return this.selectedDocuments().some(
      (document) =>
        document.type === documentType && this.uploadedDocuments.has(document),
    );
  }

  submitApplication(): void {
    if (
      this.currentStep() !== 4 ||
      this.isRegisteringAccount() ||
      this.isSubmittingApplication() ||
      this.applicationSubmitted() ||
      !this.declarationsAccepted() ||
      !this.hasRequiredDocuments()
    ) {
      return;
    }

    const account = this.buildAccountRegistrationRequest();
    const application = this.selectedAccountType() === 'business'
      ? this.buildBusinessApplicationRequest()
      : this.buildNgoApplicationRequest();

    if (!account || !application) {
      this.applicationSubmitError.set(
        'Review your account and organization details before submitting.',
      );
      return;
    }

    this.registrationError.set(null);
    this.applicationSubmitError.set(null);
    this.isSubmittingApplication.set(true);

    const createAccount$ = this.accountCreated()
      ? of(null)
      : this.registrationApi.registerAccount(account).pipe(
        tap(() => this.accountCreated.set(true)),
      );

    createAccount$.pipe(
      concatMap(() => this.registrationApi.login({
        email: account.email,
        password: account.password,
      })),
      concatMap(({ data }) => {
        const token = data.access_token;
        const draftId = this.draftApplicationId();

        const applicationId$ = draftId !== null
          ? of(draftId)
          : this.registrationApi.createApplication(application, token).pipe(
            concatMap(({ data: draft }) => {
              this.draftApplicationId.set(draft.application_id);
              return of(draft.application_id);
            }),
          );

        return applicationId$.pipe(
          concatMap((applicationId) => {
            const remainingDocuments = this.selectedDocuments().filter(
              (document) => !this.uploadedDocuments.has(document),
            );

            return from(remainingDocuments).pipe(
              concatMap((document) =>
                this.registrationApi.uploadVerificationDocument(
                  applicationId,
                  token,
                  document.type,
                  document.file,
                ).pipe(tap(() => this.uploadedDocuments.add(document))),
              ),
              startWith(null),
              last(),
              concatMap(() =>
                this.registrationApi.submitApplication(applicationId, token),
              ),
            );
          }),
        );
      }),
      takeUntilDestroyed(this.destroyRef),
      finalize(() => this.isSubmittingApplication.set(false)),
    ).subscribe({
      next: (response) => {
        if (response?.data?.status !== 'pending_verification') {
          this.applicationSubmitError.set(
            'We could not confirm submission. Check your application status.',
          );
          return;
        }

        this.applicationSubmitted.set(true);
        this.accountForm.controls.password.reset();
        this.accountForm.controls.confirmPassword.reset();
        this.selectedDocuments.set([]);
        this.uploadedDocuments.clear();
      },
      error: (response: unknown) => {
        if (!this.accountCreated()) {
          this.handleAccountRegistrationError(response);
          return;
        }

        const message = response instanceof HttpErrorResponse
          ? response.error?.error?.message
          : undefined;

        this.applicationSubmitError.set(
          typeof message === 'string' && message.trim()
            ? message.trim()
            : 'We could not submit your application. Please try again.',
        );
      },
    });
  }


}
