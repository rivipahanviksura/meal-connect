
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ResponsivePreview } from './responsive-preview';

describe('ResponsivePreview – MEAL-72', () => {
  let fixture: ComponentFixture<ResponsivePreview>;
  let element: HTMLElement;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ResponsivePreview]
    }).compileComponents();

    fixture = TestBed.createComponent(ResponsivePreview);
    fixture.detectChanges();

    element = fixture.nativeElement as HTMLElement;
  });

  it('should create the component', () => {
    expect(fixture.componentInstance).toBeTruthy();
  });

  it('should render the registration form structure', () => {
    expect(element.querySelector('.mc-form')).not.toBeNull();
    expect(element.querySelector('.mc-form-grid')).not.toBeNull();
    expect(element.querySelector('.mc-form-progress')).not.toBeNull();
  });

  it('should render labeled form fields', () => {
    const orgInput = element.querySelector('#preview-org');
    const orgLabel = element.querySelector(
      'label[for="preview-org"]'
    );

    expect(orgInput).not.toBeNull();
    expect(orgLabel).not.toBeNull();
  });

  it('should provide a labeled document upload', () => {
    const upload = element.querySelector<HTMLInputElement>(
      '#preview-document'
    );

    expect(upload?.type).toBe('file');

    expect(
      element.querySelector('label[for="preview-document"]')
    ).not.toBeNull();
  });

  it('should provide an accessible registration step indicator', () => {
    const currentStep = element.querySelector(
      '.mc-form-progress__step[aria-current="step"]'
    );

    expect(currentStep?.textContent).toContain(
      'Organization Details'
    );
  });

  it('should render responsive dashboard cards', () => {
    expect(
      element.querySelectorAll('.mc-card-grid .mc-card').length
    ).toBeGreaterThan(0);
  });

  it('should render a table inside a scroll container', () => {
    const container = element.querySelector('.mc-table-scroll');

    expect(container).not.toBeNull();
    expect(container?.querySelector('table.mc-table')).not.toBeNull();
    expect(container?.getAttribute('tabindex')).toBe('0');
  });

  it('should render a six-character PIN placeholder', () => {
    const display = element.querySelector(
      '.mc-pin-display__code'
    );

    expect(display?.textContent?.trim()).toBe('••••••');
  });

  it('should provide a labeled mobile-friendly PIN entry', () => {
    const pinInput = element.querySelector<HTMLInputElement>(
      '#preview-pin'
    );

    expect(pinInput?.getAttribute('inputmode')).toBe('numeric');
    expect(pinInput?.getAttribute('maxlength')).toBe('6');

    expect(
      element.querySelector('label[for="preview-pin"]')
    ).not.toBeNull();
  });

  it('should keep handover and distribution separate', () => {
    const stages = element.querySelectorAll('.mc-workflow-stage');

    expect(stages.length).toBe(2);

    expect(stages[0].textContent).toContain('Food Handover');
    expect(stages[1].textContent).toContain('Food Distribution');
  });

  it('should render visually distinct feedback classes', () => {
    expect(element.querySelector('.mc-feedback--loading')).not.toBeNull();
    expect(element.querySelector('.mc-feedback--success')).not.toBeNull();
    expect(element.querySelector('.mc-feedback--error')).not.toBeNull();
    expect(element.querySelector('.mc-feedback--warning')).not.toBeNull();
  });

  it('should not introduce Volunteer registration', () => {
    const options = Array.from(
      element.querySelectorAll('select option')
    ).map(option => option.textContent ?? '');

    expect(options.some(option => /volunteer/i.test(option))).toBe(false);
  });

  it('should associate validation errors with the correct field', () => {
    const input = element.querySelector<HTMLInputElement>(
      '#preview-reference'
    );

    const error = element.querySelector(
      '#preview-reference-error'
    );

    expect(input).not.toBeNull();
    expect(input?.getAttribute('aria-invalid')).toBe('true');
    expect(input?.getAttribute('aria-describedby'))
      .toBe('preview-reference-error');

    expect(error?.textContent).toContain(
      'A registration reference is required.'
    );
  });

});
