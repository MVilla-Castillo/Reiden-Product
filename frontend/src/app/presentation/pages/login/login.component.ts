import { Component, inject, OnInit } from '@angular/core';
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
export class LoginComponent implements OnInit {
  private session = inject(SessionService);
  private router = inject(Router);

  selectedUserId = 'admin@dev.local';
  sessionExpiredMessage = '';

  ngOnInit() {
    if (localStorage.getItem('session_expired')) {
      this.sessionExpiredMessage = 'Tu sesión ha expirado. Vuelve a iniciar sesión.';
      localStorage.removeItem('session_expired');
    }
  }

  login() {
    if (!this.selectedUserId) return;
    
    const isManager = this.selectedUserId === 'admin@dev.local';
    const role: UserRole = isManager ? 'manager' : 'sales';
    
    this.session.setRole(role);
    this.session.setUserId(this.selectedUserId);
    this.session.setToken('simulated-oidc-token');

    if (role === 'manager') {
      this.router.navigate(['/dashboard']);
    } else {
      this.router.navigate(['/chat']);
    }
  }
}
