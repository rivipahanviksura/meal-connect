import { Injectable, signal } from '@angular/core';

export interface SavedDraft {
  application_id: number;
  status: 'draft';
  draft_details: {
    organization_type: 'business' | 'ngo';
    business_subtype?: 'restaurant' | 'bakery';
    name: string;
    registration_number: string | null;
    contact_email: string;
    contact_phone: string | null;
    address_line: string;
    city: string;
    representative_name: string;
    representative_designation?: string | null;
    pickup_location?: string | null;
    registration_authority?: string | null;
    registration_date?: string | null;
    operational_details?: {
      operating_area?: string | null;
      distribution_area?: string | null;
      operational_capability?: string | null;
    } | null;
  };
}

export type ApplicationResumeContext = {
  email: string;
  accessToken: string;
} & (
  | { draft: SavedDraft }
  | { draft: null; accountType: 'business' | 'ngo' }
  );

@Injectable({ providedIn: 'root' })
export class ApplicationResume {
  readonly context = signal<ApplicationResumeContext | null>(null);
}
