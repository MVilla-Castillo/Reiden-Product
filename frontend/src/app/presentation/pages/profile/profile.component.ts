import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { SessionService } from '../../../core/services/session.service';
import { TopBarComponent } from '../../components/shared/top-bar.component';

@Component({
  selector: 'app-profile',
  standalone: true,
  imports: [CommonModule, FormsModule, TopBarComponent],
  template: `
    <app-top-bar title="Mi Perfil" breadcrumb="Perfil"></app-top-bar>
    <div class="profile-page">
      <div class="profile-card">
        <div class="avatar-section">
          <div class="avatar-circle">
            <span class="avatar-initials">{{ initials() }}</span>
          </div>
          <div class="role-badge" [ngClass]="isManager() ? 'manager' : 'sales'">
            {{ isManager() ? 'GERENTE' : 'VENDEDOR' }}
          </div>
        </div>

        <form class="profile-form" (ngSubmit)="saveProfile()">
          <div class="form-group">
            <label>Nombre Completo</label>
            <input type="text" [(ngModel)]="fullName" name="fullName" required>
          </div>
          
          <div class="form-group">
            <label>Correo Electrónico</label>
            <input type="email" [(ngModel)]="email" name="email" required>
          </div>
          
          <div class="form-group">
            <label>Número de WhatsApp (Twilio)</label>
            <input type="tel" [(ngModel)]="phone" name="phone">
          </div>

          <button type="submit" class="save-btn" [disabled]="isSaving()">
            {{ isSaving() ? 'Procesando...' : 'Actualizar Datos' }}
          </button>
        </form>
      </div>

      <!-- Toast Notification -->
      @if (toastMessage()) {
        <div class="toast-notification" [ngClass]="toastType()">
          <span class="toast-icon">{{ toastType() === 'warning' ? '⚠️' : '✅' }}</span>
          {{ toastMessage() }}
        </div>
      }
    </div>
  `,
  styles: [`
    .profile-page { padding: 2rem; max-width: 600px; margin: 0 auto; position: relative; }
    .page-header { margin-bottom: 2rem; h1 { font-size: 1.8rem; margin: 0 0 0.5rem; } p { color: #6b7280; margin: 0; } }
    
    .profile-card { background: white; border-radius: 16px; padding: 2rem; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }
    
    .avatar-section { display: flex; flex-direction: column; align-items: center; margin-bottom: 2rem; }
    .avatar-circle { width: 96px; height: 96px; border-radius: 50%; background: linear-gradient(135deg, #e0e7ff, #c7d2fe); display: flex; align-items: center; justify-content: center; margin-bottom: 1rem; }
    .avatar-initials { font-size: 2.5rem; font-weight: 700; color: #4f46e5; }
    
    .role-badge { padding: 4px 12px; border-radius: 99px; font-size: 0.75rem; font-weight: 700; letter-spacing: 1px; }
    .role-badge.manager { background: #fee2e2; color: #b91c1c; }
    .role-badge.sales { background: #dcfce7; color: #15803d; }

    .profile-form .form-group { margin-bottom: 1.5rem; }
    .form-group label { display: block; margin-bottom: 0.5rem; font-size: 0.875rem; font-weight: 500; color: #374151; }
    .form-group input { width: 100%; padding: 0.75rem 1rem; border: 1px solid #d1d5db; border-radius: 8px; box-sizing: border-box; font-family: inherit; transition: border-color 0.2s; }
    .form-group input:focus { outline: none; border-color: #4f46e5; box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1); }

    .save-btn { width: 100%; padding: 0.875rem; background: var(--primary-color, #4f46e5); color: white; border: none; border-radius: 8px; font-weight: 600; font-family: inherit; cursor: pointer; transition: opacity 0.2s; }
    .save-btn:hover { opacity: 0.9; }
    .save-btn:disabled { opacity: 0.5; cursor: not-allowed; }

    /* Toast */
    .toast-notification {
      position: absolute; top: 1rem; right: 1rem; padding: 1rem 1.5rem; border-radius: 8px; display: flex; align-items: center; gap: 0.75rem; font-weight: 500; font-size: 0.95rem; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); animation: slideIn 0.3s cubic-bezier(0.16, 1, 0.3, 1);
    }
    .toast-notification.success { background: #ecfdf5; color: #065f46; border-left: 4px solid #10b981; }
    .toast-notification.warning { background: #fffbeb; color: #92400e; border-left: 4px solid #f59e0b; }

    @keyframes slideIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
  `]
})
export class ProfileComponent {
  session = inject(SessionService);

  fullName = 'Juan Demo';
  email = 'juan@automotora.com';
  phone = '+123456789';

  isSaving = signal(false);
  toastMessage = signal<string | null>(null);
  toastType = signal<'success' | 'warning'>('success');

  isManager() {
    return this.session.currentRole() === 'manager';
  }

  initials() {
    return this.fullName.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();
  }

  saveProfile() {
    this.isSaving.set(true);

    // Simulate API Call
    setTimeout(() => {
      this.isSaving.set(false);
      
      if (this.isManager()) {
        this.toastType.set('success');
        this.toastMessage.set('Perfil actualizado exitosamente.');
      } else {
        this.toastType.set('warning');
        this.toastMessage.set('Cambios encolados. Requieren aprobación gerencial para aplicarse sobre tu agente Twilio.');
      }

      // Hide toast after 4s
      setTimeout(() => this.toastMessage.set(null), 4000);
    }, 800);
  }
}
