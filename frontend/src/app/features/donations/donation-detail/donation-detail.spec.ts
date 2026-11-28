import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { DonationDetailComponent } from './donation-detail';

describe('DonationDetailComponent', () => {
  let component: DonationDetailComponent;
  let fixture: ComponentFixture<DonationDetailComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [DonationDetailComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([])
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(DonationDetailComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create the donation detail component', () => {
    expect(component).toBeTruthy();
  });

  it('should keep claim disabled until all feasibility checks are checked', () => {
    expect(component.canSubmitClaim()).toBe(false);

    component.checks.coldStorageReady = true;
    component.checks.vehicleFits = true;
    component.checks.allergenChecked = true;

    expect(component.canSubmitClaim()).toBe(true);
  });
});
