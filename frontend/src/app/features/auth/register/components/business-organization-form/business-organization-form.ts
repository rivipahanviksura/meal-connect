import { Component, input, output } from '@angular/core';
import {
  FormControl,
  FormGroup,
  ReactiveFormsModule,
} from '@angular/forms';

type BusinessOrganizationControls = {
  businessName: FormControl<string>;
  registrationNumber: FormControl<string>;
  businessType: FormControl<string>;
  registeredAddress: FormControl<string>;
  city: FormControl<string>;
  pickupLocation: FormControl<string>;
  contactEmail: FormControl<string>;
  contactPhone: FormControl<string>;
  representativeDesignation: FormControl<string>;
};

@Component({
  selector: 'app-business-organization-form',
  standalone: true,
  imports: [ReactiveFormsModule],
  templateUrl: './business-organization-form.html',
  styleUrl: './business-organization-form.scss',
})
export class BusinessOrganizationForm {
  readonly form = input.required<FormGroup<BusinessOrganizationControls>>();
  readonly resumeRepresentativeName = input.required<FormControl<string>>();
  readonly showResumeRepresentativeName = input(false);

  readonly backRequested = output<void>();
  readonly validateRequested = output<void>();
}
