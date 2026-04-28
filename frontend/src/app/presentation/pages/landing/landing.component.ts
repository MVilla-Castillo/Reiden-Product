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

  readonly implementationPhases = [
    {
      label: 'Semana 1',
      title: 'Diagnostico comercial',
      description:
        'Mapeamos tu flujo actual por sucursal, objetivos de conversion y puntos de fuga de leads.'
    },
    {
      label: 'Semanas 2-3',
      title: 'Configuracion y puesta en marcha',
      description:
        'Activamos usuarios, reglas operativas y estructura de seguimiento para ordenar el equipo.'
    },
    {
      label: 'Semana 4',
      title: 'Acompanamiento y optimizacion',
      description:
        'Revisamos adopcion, ajustamos el flujo real de trabajo y afinamos indicadores de gestion.'
    }
  ];

  readonly commitments = [
    {
      title: 'Sin friccion para el equipo',
      description: 'Implementacion guiada para que vendedores y gerencia adopten el sistema rapidamente.'
    },
    {
      title: 'Control gerencial desde el dia 1',
      description: 'Estandarizamos el seguimiento para que cada sucursal opere con criterio comun.'
    },
    {
      title: 'Soporte y mejora continua',
      description: 'No solo activamos la plataforma, tambien acompanamos su evolucion en terreno.'
    }
  ];
}
