import { Component, input, output } from '@angular/core';
import {
  FormControl,
  FormGroup,
  ReactiveFormsModule,
} from '@angular/forms';

type NgoOrganizationControls = {
  ngoName: FormControl<string>;
  registrationNumber: FormControl<string>;
  registrationAuthority: FormControl<string>;
  registrationDate: FormControl<string>;
  registeredAddress: FormControl<string>;
  city: FormControl<string>;
  operatingArea: FormControl<string>;
  contactEmail: FormControl<string>;
  contactPhone: FormControl<string>;
  representativeDesignation: FormControl<string>;
  distributionArea: FormControl<string>;
  operationalCapability: FormControl<string>;
};

@Component({
  selector: 'app-ngo-organization-form',
  standalone: true,
  imports: [ReactiveFormsModule],
  templateUrl: './ngo-organization-form.html',
  styleUrl: './ngo-organization-form.scss',
})
export class NgoOrganizationForm {
  readonly form = input.required<FormGroup<NgoOrganizationControls>>();
  readonly resumeRepresentativeName = input.required<FormControl<string>>();
  readonly showResumeRepresentativeName = input(false);

  readonly backRequested = output<void>();
  readonly validateRequested = output<void>();
}
