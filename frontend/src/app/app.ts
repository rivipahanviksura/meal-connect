
import { Component, inject } from '@angular/core';
import { RouterOutlet } from '@angular/router';

import { Header } from './shared/layout/header/header';
import { Footer } from './shared/layout/footer/footer';
import { Sidebar } from './shared/layout/sidebar/sidebar';
import { NavigationSessionService } from './core/services/navigation-session';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, Header, Footer, Sidebar],
  templateUrl: './app.html',
  styleUrl: './app.scss'
})
export class App {
  protected readonly navigationSession = inject(NavigationSessionService);

  protected readonly account = this.navigationSession.account;
}
