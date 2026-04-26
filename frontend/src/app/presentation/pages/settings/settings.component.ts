import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TopBarComponent } from '../../components/shared/top-bar.component';

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [CommonModule, TopBarComponent],
  template: `
    <app-top-bar title="Configuración" breadcrumb="Ajustes"></app-top-bar>
    <div class="settings-page">
      <div class="settings-card">
        <h3>Tema y Colores Primarios</h3>
        <p class="description">Selecciona un color de acento para los botones y elementos activos del sistema.</p>
        
        <div class="color-palette">
          <button class="color-btn indigo" (click)="setPrimaryColor('#4f46e5')" title="Índigo Corporativo"></button>
          <button class="color-btn emerald" (click)="setPrimaryColor('#10b981')" title="Verde Esmeralda"></button>
          <button class="color-btn pink" (click)="setPrimaryColor('#db2777')" title="Rosa Neón"></button>
          <button class="color-btn amber" (click)="setPrimaryColor('#d97706')" title="Ámbar"></button>
          <button class="color-btn slate" (click)="setPrimaryColor('#475569')" title="Gris Pizarra"></button>
        </div>

        <div class="preview-box">
          <p>Vista previa del color seleccionado:</p>
          <button class="preview-btn" [style.background-color]="currentColor">Botón Principal</button>
          <button class="preview-btn-outline" [style.border-color]="currentColor" [style.color]="currentColor">Botón Secundario</button>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .settings-page { padding: 2rem; max-width: 800px; margin: 0 auto; }
    .page-header { margin-bottom: 2rem; h1 { font-size: 1.8rem; margin: 0 0 0.5rem; } p { color: #6b7280; margin: 0; } }
    
    .settings-card {
      background: white; border-radius: 12px; padding: 2rem; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
      h3 { margin-top: 0; color: #111827; }
      .description { color: #6b7280; margin-bottom: 1.5rem; font-size: 0.95rem; }
    }

    .color-palette {
      display: flex; gap: 1rem; margin-bottom: 2rem;
    }
    
    .color-btn {
      width: 48px; height: 48px; border-radius: 50%; border: 3px solid transparent; cursor: pointer;
      transition: transform 0.2s, border-color 0.2s;
      &:hover { transform: scale(1.1); }
      &.indigo { background: #4f46e5; }
      &.emerald { background: #10b981; }
      &.pink { background: #db2777; }
      &.amber { background: #d97706; }
      &.slate { background: #475569; }
    }

    .preview-box {
      padding: 1.5rem; background: #f8fafc; border-radius: 8px; border: 1px dashed #cbd5e1;
      p { font-size: 0.9rem; color: #64748b; margin-bottom: 1rem; margin-top: 0; }
      display: flex; gap: 1rem;
    }

    .preview-btn {
      padding: 10px 20px; color: white; border: none; border-radius: 8px; font-weight: 600; cursor: pointer; transition: opacity 0.2s;
      &:hover { opacity: 0.9; }
    }
    
    .preview-btn-outline {
      padding: 10px 20px; background: transparent; border: 2px solid; border-radius: 8px; font-weight: 600; cursor: pointer;
    }
  `]
})
export class SettingsComponent {
  currentColor = '#4f46e5';

  setPrimaryColor(color: string) {
    this.currentColor = color;
    // Inject the selected color to a global CSS variable dynamically onto the app's root scope.
    // Assuming the app elements bind to var(--primary-color, #4f46e5)
    document.documentElement.style.setProperty('--primary-color', color);
    
    // As a demonstration for previously hardcoded elements:
    const dynamicStyles = document.getElementById('dynamic-theme') || document.createElement('style');
    dynamicStyles.id = 'dynamic-theme';
    dynamicStyles.innerHTML = [
      '.login-submit, button.active, .role-btn.active .active-indicator, .chat-window button { background: ' + color + ' !important; border-color: ' + color + ' !important; }',
      '.role-btn.active { color: ' + color + ' !important; border-color: ' + color + ' !important; }',
      '.role-btn.active .role-title { color: ' + color + ' !important; }'
    ].join('\\n');
    document.head.appendChild(dynamicStyles);
  }
}
