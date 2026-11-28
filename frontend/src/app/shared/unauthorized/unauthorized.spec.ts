
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { Unauthorized } from './unauthorized';

describe('Unauthorized – MEAL-71', () => {
  let fixture: ComponentFixture<Unauthorized>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Unauthorized],
      providers: [provideRouter([])]
    }).compileComponents();

    fixture = TestBed.createComponent(Unauthorized);
    fixture.detectChanges();
  });

  it('should create the component', () => {
    expect(fixture.componentInstance).toBeTruthy();
  });

  it('should display access denied message', () => {
    const element = fixture.nativeElement as HTMLElement;

    expect(element.textContent).toContain('403');
    expect(element.textContent).toContain('Access Denied');
    expect(element.textContent).toContain(
      "You don't have permission"
    );
  });

  it('should provide a link back to Home', () => {
    const element = fixture.nativeElement as HTMLElement;

    const link = element.querySelector<HTMLAnchorElement>(
      'a.home-link'
    );

    expect(link).not.toBeNull();
    expect(link?.getAttribute('href')).toBe('/');
  });
});
