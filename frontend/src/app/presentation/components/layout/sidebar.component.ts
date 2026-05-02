import { Component, inject, signal, computed } from '@angular/core';
import { Router, RouterModule } from '@angular/router';
import { SessionService } from '../../../core/services/session.service';
import { IconComponent } from '../../components/shared/icons.component';
import { CrmApiService } from '../../../infrastructure/repositories/crm.api.service';
import { supabase } from '../../../core/supabase';

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [RouterModule, IconComponent],
  templateUrl: './sidebar.component.html',
  styleUrl: './sidebar.component.scss'
})
export class SidebarComponent {
  session = inject(SessionService);
  private router = inject(Router);
  private crmApi = inject(CrmApiService);

  tenantName = signal<string>('');

  constructor() {
    this.crmApi.getTenantSettings().subscribe({
      next: (settings) => this.tenantName.set(settings.nombre_legal),
      error: () => this.tenantName.set('—')
    });
  }

  userInitial = computed(() => this.session.userId()?.charAt(0).toUpperCase() ?? '?');

  navItems = [
    { icon: 'chart-bar', label: 'Dashboard', route: '/dashboard', roles: ['manager'] },
    { icon: 'users', label: 'Leads', route: '/leads', roles: ['manager', 'sales'] },
    { icon: 'chat-bubble-left-right', label: 'Conversaciones', route: '/chat', roles: ['manager', 'sales'] },
    { icon: 'presentation-chart-line', label: 'Reportes', route: '/reports', roles: ['manager'] },
  ];

  async logout() {
    await supabase.auth.signOut();
    this.session.clear();
    this.router.navigate(['/login']);
  }
}