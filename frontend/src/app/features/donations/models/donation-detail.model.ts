export interface DonationItem {
  name: string;
  quantity: string;
  weightKg: number;
  storageTemp: string;
  expiryTime: string;
}

export interface DonationPermissions {
  canViewPickupAddress: boolean;
  canViewContactDetails: boolean;
  canClaim: boolean;
  userRole: 'VERIFIED_NGO' | 'UNVERIFIED_NGO' | 'DONOR' | 'GUEST';
}

export interface DonationDetail {
  id: string;
  title: string;
  status: 'AVAILABLE' | 'CLAIMED' | 'EXPIRED';
  category: string;
  totalServings: number;
  totalWeightKg: number;
  pickupDeadline: string;
  storageType: 'REFRIGERATED' | 'FROZEN' | 'AMBIENT';
  temperatureRange: string;
  allergens: string[];
  dietaryTags: string[];
  items: DonationItem[];
  organization: {
    id: string;
    name: string;
    verified: boolean;
    rating: number;
  };
  pickupLocation: {
    generalArea: string;
    exactAddress?: string;
    accessInstructions?: string;
    contactPerson?: string;
    contactPhone?: string;
  };
  permissions: DonationPermissions;
}
