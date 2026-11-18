
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
      import('./features/auth/login/login')
        .then(m => m.Login)
  },

  {
    path: 'register',
    title: 'Register | Meal Connect',
    loadComponent: () =>
      import('./features/auth/register/register')
        .then(m => m.Register)
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
