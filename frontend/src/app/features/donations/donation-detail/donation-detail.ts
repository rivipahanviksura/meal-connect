import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterModule } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { DonationDetailApi, ApiErrorState } from '../services/donation-detail-api';
import { DonationDetail } from '../models/donation-detail.model';

@Component({
  selector: 'app-donation-detail',
  standalone: true,
  imports: [CommonModule, RouterModule, FormsModule],
  templateUrl: './donation-detail.html',
  styleUrl: './donation-detail.scss',
})
export class DonationDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private donationApi = inject(DonationDetailApi);

  donation = signal<DonationDetail | null>(null);
  loading = signal<boolean>(true);
  error = signal<ApiErrorState | null>(null);
  claiming = signal<boolean>(false);
  claimSuccessRef = signal<string | null>(null);

  checks = {
    coldStorageReady: false,
    vehicleFits: false,
    allergenChecked: false
  };

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id');
    if (id) {
      this.loadDonation(id);
    } else {
      this.loading.set(false);
      this.error.set({
        status: 404,
        title: 'Invalid Link',
        message: 'No donation ID was provided in the URL.'
      });
    }
  }

  retryLoad(): void {
    const id = this.route.snapshot.paramMap.get('id');
    if (id) {
      this.loadDonation(id);
    }
  }

  loadDonation(id: string): void {
    this.loading.set(true);
    this.error.set(null);

    this.donationApi.getDonationById(id).subscribe({
      next: (data) => {
        this.donation.set(data);
        this.loading.set(false);
      },
      error: (err: ApiErrorState) => {
        this.error.set(err);
        this.loading.set(false);
      }
    });
  }

  canSubmitClaim(): boolean {
    return this.checks.coldStorageReady && this.checks.vehicleFits && this.checks.allergenChecked;
  }

  submitClaim(): void {
    const current = this.donation();
    if (!current || !this.canSubmitClaim()) return;

    this.claiming.set(true);
    this.donationApi.claimDonation(current.id, 'Confirmed cold-chain & transport').subscribe({
      next: (res) => {
        this.claiming.set(false);
        this.claimSuccessRef.set(res.claimReference);
        this.donation.set({ ...current, status: 'CLAIMED' });
      },
      error: (err: ApiErrorState) => {
        this.claiming.set(false);
        this.error.set(err);
      }
    });
  }
}
