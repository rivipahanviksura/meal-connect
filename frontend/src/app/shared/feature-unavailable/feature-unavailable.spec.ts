
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { FeatureUnavailable } from './feature-unavailable';

describe('FeatureUnavailable – MEAL-71', () => {
  let fixture: ComponentFixture<FeatureUnavailable>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [FeatureUnavailable],
      providers: [provideRouter([])]
    }).compileComponents();

    fixture = TestBed.createComponent(FeatureUnavailable);
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(fixture.componentInstance).toBeTruthy();
  });

  it('should show unavailable message and Home link', () => {
    const element = fixture.nativeElement as HTMLElement;

    expect(element.textContent).toContain('Page Not Available Yet');
    expect(element.querySelector('a')?.getAttribute('href')).toBe('/');
  });
});
