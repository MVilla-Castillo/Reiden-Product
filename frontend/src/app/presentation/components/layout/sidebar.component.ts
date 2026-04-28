import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterModule } from '@angular/router';
import { SessionService } from '../../../core/services/session.service';
import { IconComponent } from '../../components/shared/icons.component';

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [CommonModule, RouterModule, IconComponent],
  templateUrl: './sidebar.component.html',
  styleUrl: './sidebar.component.scss'
})
export class SidebarComponent {
  session = inject(SessionService);
  private router = inject(Router);

  navItems = [
    { icon: 'chart-bar', label: 'Dashboard', route: '/dashboard', active: true, roles: ['manager'] },
    { icon: 'users', label: 'Leads', route: '/leads', active: false, roles: ['manager', 'sales'] },
    { icon: 'chat-bubble-left-right', label: 'Conversaciones', route: '/chat', active: false, roles: ['manager', 'sales'] },
    { icon: 'presentation-chart-line', label: 'Reportes', route: '/reports', active: false, roles: ['manager'] },
  ];

  setRole(role: 'manager' | 'sales') {
    this.session.setRole(role);
    if (role === 'manager') {
      this.router.navigate(['/dashboard']);
    } else {
      this.router.navigate(['/leads']);
    }
  }
}