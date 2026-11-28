
import { Injectable, computed, signal } from '@angular/core';
import type {
  NavigationAccount,
  NavigationSession
} from '../models/navigation-account';

@Injectable({
  providedIn: 'root'
})
export class NavigationSessionService {
  private readonly state = signal<NavigationSession>({
    status: 'anonymous'
  });

  readonly session = this.state.asReadonly();

  readonly account = computed<NavigationAccount | null>(() => {
    const current = this.state();

    return current.status === 'authenticated'
      ? current.account
      : null;
  });

  readonly isAuthenticated = computed(() => {
    const account = this.account();
    return account !== null && account.isActive;
  });

  setAuthenticatedAccount(account: NavigationAccount): void {
    // Only the trusted authentication integration should call this
    // with an account resolved from the backend.
    this.state.set({
      status: 'authenticated',
      account
    });
  }

  setAnonymous(): void {
    this.state.set({ status: 'anonymous' });
  }

  setLoading(): void {
    this.state.set({ status: 'loading' });
  }

  setError(): void {
    this.state.set({ status: 'error' });
  }

  clear(): void {
    this.setAnonymous();
  }
}
