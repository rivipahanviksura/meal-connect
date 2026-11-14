
import { Component, input, output } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';

@Component({
  selector: 'app-header',
  imports: [RouterLink, RouterLinkActive],
  templateUrl: './header.html',
  styleUrl: './header.scss'
})
export class Header {
  readonly isAuthenticated = input(false);
  readonly logoutEnabled = input(false);

  readonly logoutRequested = output<void>();

  requestLogout(): void {
    if (this.isAuthenticated() && this.logoutEnabled()) {
      this.logoutRequested.emit();
    }
  }
}
