import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterModule } from '@angular/router';
import { SessionService } from '../../../core/services/session.service';

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [CommonModule, RouterModule],
  templateUrl: './sidebar.component.html',
  styleUrl: './sidebar.component.scss'
})
export class SidebarComponent {
  session = inject(SessionService);
  private router = inject(Router);

  navItems = [
    { icon: '📊', label: 'Dashboard', route: '/dashboard', active: true, roles: ['manager'] },
    { icon: '👥', label: 'Leads', route: '/leads', active: false, roles: ['manager'] },
    { icon: '💬', label: 'Conversaciones', route: '/chat', active: false, roles: ['manager', 'sales'] },
    { icon: '📈', label: 'Reportes', route: '/reports', active: false, roles: ['manager'] },
  ];

  setRole(role: 'manager' | 'sales') {
    this.session.setRole(role);
    if (role === 'manager') {
      this.router.navigate(['/dashboard']);
    } else {
      this.router.navigate(['/chat']);
    }
  }
}