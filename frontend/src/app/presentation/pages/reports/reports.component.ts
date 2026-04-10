import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-reports',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="reports-page">
      <header class="page-header">
        <h1>Reportes de Rendimiento</h1>
        <p>Métricas y analytics en tiempo real de tu equipo comercial.</p>
      </header>

      <div class="charts-grid">
        <div class="chart-card">
          <h3>Tasa de Conversión (Últimos 7 días)</h3>
          <div class="bars-container">
            <div class="bar-group">
              <div class="bar bg-indigo" style="height: 40%"><span>L</span></div>
              <div class="bar bg-indigo" style="height: 65%"><span>M</span></div>
              <div class="bar bg-pink" style="height: 35%"><span>M</span></div>
              <div class="bar bg-indigo" style="height: 90%"><span>J</span></div>
              <div class="bar bg-pink" style="height: 70%"><span>V</span></div>
              <div class="bar bg-indigo" style="height: 50%"><span>S</span></div>
              <div class="bar bg-indigo" style="height: 25%"><span>D</span></div>
            </div>
          </div>
        </div>

        <div class="chart-card">
          <h3>Rendimiento por Vendedor (Cierres)</h3>
          <div class="horizontal-bars">
            <div class="h-bar-row">
              <span class="label">Carlos M.</span>
              <div class="h-bar-track"><div class="h-bar bg-sky" style="width: 85%"></div></div>
              <span class="value">85%</span>
            </div>
            <div class="h-bar-row">
              <span class="label">Ana P.</span>
              <div class="h-bar-track"><div class="h-bar bg-pink" style="width: 60%"></div></div>
              <span class="value">60%</span>
            </div>
            <div class="h-bar-row">
              <span class="label">Julio G.</span>
              <div class="h-bar-track"><div class="h-bar bg-emerald" style="width: 40%"></div></div>
              <span class="value">40%</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .reports-page { padding: 2rem; max-width: 1400px; margin: 0 auto; }
    .page-header {
      margin-bottom: 2rem;
      h1 { font-size: 1.8rem; color: #111827; margin: 0 0 0.5rem; }
      p { color: #6b7280; margin: 0; }
    }
    
    .charts-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 1.5rem; }
    .chart-card {
      background: white; border-radius: 12px; padding: 1.5rem;
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
      h3 { margin-top: 0; color: #374151; font-size: 1.1rem; border-bottom: 1px solid #f3f4f6; padding-bottom: 0.75rem; margin-bottom: 1.5rem;}
    }

    /* Vertical Bars Simulation */
    .bars-container { height: 200px; display: flex; align-items: flex-end; padding-top: 1rem; }
    .bar-group { display: flex; justify-content: space-between; width: 100%; height: 100%; align-items: flex-end; }
    .bar {
      width: 12%; border-radius: 6px 6px 0 0; position: relative;
      transition: height 1s ease-in-out;
      span { position: absolute; bottom: -25px; left: 50%; transform: translateX(-50%); font-size: 0.8rem; color: #6b7280; font-weight: 500;}
      &:hover { filter: brightness(1.1); }
    }

    /* Horizontal Bars Simulation */
    .horizontal-bars { display: flex; flex-direction: column; gap: 1.25rem; }
    .h-bar-row { display: flex; align-items: center; gap: 1rem; }
    .label { width: 80px; font-size: 0.9rem; font-weight: 500; color: #4b5563; }
    .h-bar-track { flex: 1; height: 12px; background: #f3f4f6; border-radius: 6px; overflow: hidden; }
    .h-bar { height: 100%; border-radius: 6px; transition: width 1s ease-in-out; }
    .value { width: 40px; font-size: 0.9rem; font-weight: 600; color: #111827; text-align: right; }

    /* Colors */
    .bg-indigo { background: #4f46e5; }
    .bg-pink { background: #ec4899; }
    .bg-sky { background: #0ea5e9; }
    .bg-emerald { background: #10b981; }
  `]
})
export class ReportsComponent {
}
