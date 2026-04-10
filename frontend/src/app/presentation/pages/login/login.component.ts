import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { SessionService, UserRole } from '../../../core/services/session.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './login.component.html',
  styleUrl: './login.component.scss'
})
export class LoginComponent {
  private session = inject(SessionService);
  private router = inject(Router);

  role: UserRole = 'manager';

  login() {
    this.session.setRole(this.role);
    this.session.setToken('simulated-oidc-token');

    if (this.role === 'manager') {
      this.router.navigate(['/dashboard']);
    } else {
      this.router.navigate(['/chat']);
    }
  }
}
