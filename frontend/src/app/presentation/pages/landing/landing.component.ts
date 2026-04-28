import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-landing',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './landing.component.html',
  styleUrl: './landing.component.scss'
})
export class LandingComponent {
  readonly trustLogos = [
    'Automotora Norte',
    'Grupo Ruta Sur',
    'Motors Prime',
    'AutoCenter CL',
    'Capital Autos'
  ];

  readonly painPoints = [
    'Leads que se enfrían por falta de seguimiento y respuesta tardía.',
    'WhatsApp, planillas y notas separadas que rompen el flujo comercial.',
    'Poca visibilidad del desempeño por sucursal y por vendedor.'
  ];

  readonly benefits = [
    {
      title: 'Control total por sucursal',
      description:
        'Visualiza rendimiento y carga de trabajo por punto de venta con una vista centralizada para gerencia.'
    },
    {
      title: 'Reportes de rendimiento',
      description:
        'Métricas claras para tomar decisiones: estado de leads, tiempos de respuesta y cierres por equipo.'
    },
    {
      title: 'Flujo comercial ordenado',
      description:
        'Cada lead avanza con contexto completo para evitar tareas manuales y minimizar pérdidas de oportunidad.'
    }
  ];
}
