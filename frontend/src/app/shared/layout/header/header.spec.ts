
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { Header } from './header';

describe('Header – MEAL-71', () => {
  let fixture: ComponentFixture<Header>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Header],
      providers: [provideRouter([])]
    }).compileComponents();

    fixture = TestBed.createComponent(Header);
    fixture.detectChanges();
  });

  function element(): HTMLElement {
    return fixture.nativeElement as HTMLElement;
  }

  it('should create the component', () => {
    expect(fixture.componentInstance).toBeTruthy();
  });

  it('should show public navigation by default', () => {
    const text = element().querySelector('nav')?.textContent ?? '';

    expect(text).toContain('Home');
    expect(text).toContain('Login');
    expect(text).toContain('Register');
  });

  it('should not show Logout to public users', () => {
    expect(
      element().querySelector('.logout-button')
    ).toBeNull();
  });

  it('should hide Login and Register for authenticated users', () => {
    fixture.componentRef.setInput('isAuthenticated', true);
    fixture.detectChanges();

    const text = element().querySelector('nav')?.textContent ?? '';

    expect(text).toContain('Home');
    expect(text).not.toContain('Login');
    expect(text).not.toContain('Register');
    expect(text).toContain('Logout');
  });

  it('should disable Logout until authentication integration exists', () => {
    fixture.componentRef.setInput('isAuthenticated', true);
    fixture.detectChanges();

    const button = element().querySelector<HTMLButtonElement>(
      '.logout-button'
    );

    expect(button).not.toBeNull();
    expect(button?.disabled).toBe(true);
  });

  it('should emit logoutRequested when enabled and clicked', () => {
    fixture.componentRef.setInput('isAuthenticated', true);
    fixture.componentRef.setInput('logoutEnabled', true);
    fixture.detectChanges();

    let emitted = 0;

    fixture.componentInstance.logoutRequested.subscribe(() => {
      emitted++;
    });

    const button = element().querySelector<HTMLButtonElement>(
      '.logout-button'
    );

    button?.click();

    expect(emitted).toBe(1);
  });

  it('should not emit logoutRequested when disabled', () => {
    fixture.componentRef.setInput('isAuthenticated', true);
    fixture.componentRef.setInput('logoutEnabled', false);
    fixture.detectChanges();

    let emitted = 0;

    fixture.componentInstance.logoutRequested.subscribe(() => {
      emitted++;
    });

    const button = element().querySelector<HTMLButtonElement>(
      '.logout-button'
    );

    button?.click();

    expect(emitted).toBe(0);
  });

  it('should not emit logoutRequested for public users', () => {
    fixture.componentRef.setInput('logoutEnabled', true);
    fixture.detectChanges();

    let emitted = 0;

    fixture.componentInstance.logoutRequested.subscribe(() => {
      emitted++;
    });

    fixture.componentInstance.requestLogout();

    expect(emitted).toBe(0);
  });
});
