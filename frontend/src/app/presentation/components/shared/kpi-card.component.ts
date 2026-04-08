import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-kpi-card',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="kpi-card" [class.critical]="critical">
      <div class="kpi-icon">{{ icon }}</div>
      <div class="kpi-content">
        <div class="kpi-value">{{ value }}</div>
        <div class="kpi-label">{{ label }}</div>
      </div>
    </div>
  `,
  styles: [`
    :host {
      display: block;
    }
    
    .kpi-card {
      background: white;
      border-radius: 16px;
      padding: 1.5rem;
      display: flex;
      align-items: center;
      gap: 1rem;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
      transition: all 0.2s ease;
      cursor: pointer;
      
      &:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
      }
      
      &.critical {
        background: linear-gradient(135deg, #fef2f2 0%, #fff 100%);
        border: 1px solid #fecaca;
        
        .kpi-value {
          color: #dc2626;
        }
      }
    }
    
    .kpi-icon {
      width: 56px;
      height: 56px;
      border-radius: 14px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 1.5rem;
      background: #f3f4f6;
    }
    
    .kpi-content {
      flex: 1;
    }
    
    .kpi-value {
      font-size: 2rem;
      font-weight: 700;
      color: #111827;
      line-height: 1;
    }
    
    .kpi-label {
      font-size: 0.875rem;
      color: #6b7280;
      margin-top: 0.25rem;
    }
  `]
})
export class KpiCardComponent {
  @Input() icon = '';
  @Input() value = 0;
  @Input() label = '';
  @Input() critical = false;
}