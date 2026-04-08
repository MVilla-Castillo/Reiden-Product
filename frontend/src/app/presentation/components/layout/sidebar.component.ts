import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { SessionService } from '../../../core/services/session.service';

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './sidebar.component.html',
  styleUrl: './sidebar.component.scss'
})
export class SidebarComponent {
  session = inject(SessionService);

  navItems = [
    { icon: '📊', label: 'Dashboard', route: '/dashboard', active: true },
    { icon: '👥', label: 'Leads', route: '/leads', active: false },
    { icon: '💬', label: 'Conversaciones', route: '/conversations', active: false },
    { icon: '📈', label: 'Reportes', route: '/reports', active: false },
  ];

  setRole(role: 'manager' | 'sales') {
    this.session.setRole(role);
  }
}