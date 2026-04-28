import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { IconComponent } from './icons.component';

@Component({
  selector: 'app-kpi-card',
  standalone: true,
  imports: [CommonModule, IconComponent],
  template: `
    <div class="kpi-card" [class.critical]="critical">
      <div class="kpi-accent"></div>
      <div class="kpi-inner">
        <div class="kpi-header">
          <app-icon [name]="icon" [size]="18" [cssClass]="'kpi-icon-bg'"></app-icon>
          <span class="kpi-label">{{ label }}</span>
        </div>
        <div class="kpi-value-row">
          <div class="kpi-value">{{ value }}</div>
          @if (trend) {
            <div class="kpi-trend" [class.positive]="trend.startsWith('+')" [class.negative]="trend.startsWith('-')">
              {{ trend }}
            </div>
          }
        </div>
      </div>
    </div>
  `,
  styles: [`
    :host {
      display: block;
    }
    
    .kpi-card {
      background: white;
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
      transition: all 0.2s ease;
      cursor: pointer;
      position: relative;
      
      &:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
      }
      
      &.critical {
        .kpi-accent {
          background: #ef4444;
        }
        .kpi-value {
          color: #dc2626;
        }
      }
    }
    
    .kpi-accent {
      height: 3px;
      background: #3b82f6;
    }
    
    .kpi-inner {
      padding: 1rem 1.25rem 1.25rem;
    }
    
    .kpi-header {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      margin-bottom: 0.5rem;
    }
    
    ::ng-deep .kpi-icon-bg {
      color: #3b82f6;
    }
    
    .kpi-label {
      font-size: 0.8125rem;
      color: #64748b;
      font-weight: 500;
    }
    
    .kpi-value-row {
      display: flex;
      align-items: baseline;
      gap: 0.5rem;
    }
    
    .kpi-value {
      font-size: 1.75rem;
      font-weight: 700;
      color: #0f172a;
      line-height: 1.1;
    }
    
    .kpi-trend {
      font-size: 0.75rem;
      font-weight: 600;
      padding: 2px 6px;
      border-radius: 4px;
      background: #f1f5f9;
      color: #475569;
    }
    .kpi-trend.positive {
      background: #dcfce7;
      color: #166534;
    }
    .kpi-trend.negative {
      background: #fee2e2;
      color: #991b1b;
    }
  `]
})
export class KpiCardComponent {
  @Input() icon = '';
  @Input() value: number | string = 0;
  @Input() trend?: string = '';
  @Input() label = '';
  @Input() critical = false;
}