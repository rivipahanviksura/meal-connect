
import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    title: 'Home | Meal Connect',
    loadComponent: () =>
      import('./features/home/home').then(m => m.Home)
  },
  {
    path: 'login',
    title: 'Login | Meal Connect',
    loadComponent: () =>
      import('./shared/feature-unavailable/feature-unavailable')
        .then(m => m.FeatureUnavailable)
  },
  {
    path: 'register',
    title: 'Register | Meal Connect',
    loadComponent: () =>
      import('./shared/feature-unavailable/feature-unavailable')
        .then(m => m.FeatureUnavailable)
  },

  {
    path: 'unauthorized',
    title: 'Access Denied | Meal Connect',
    loadComponent: () =>
      import('./shared/unauthorized/unauthorized')
        .then(m => m.Unauthorized)
  },
  {
    path: '**',
    redirectTo: ''
  }
];
