import { CommonModule } from '@angular/common';
import { Component, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-contacto',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './contacto.component.html',
  styleUrl: './contacto.component.scss'
})
export class ContactoComponent {
  readonly subjectOptions = [
    'Consulta general',
    'Solicitar demo',
    'Quiero ser cliente',
    'Soporte tecnico',
    'Otro'
  ];

  name = signal('');
  email = signal('');
  subject = signal('');
  message = signal('');
  isLoading = signal(false);
  submitted = signal(false);
  errorMessage = signal('');

  onSubmit() {
    if (!this.name() || !this.email() || !this.message()) {
      this.errorMessage.set('Por favor completa los campos obligatorios.');
      return;
    }

    this.isLoading.set(true);
    this.errorMessage.set('');

    // TODO: conectar con endpoint real de contacto
    setTimeout(() => {
      this.isLoading.set(false);
      this.submitted.set(true);
      this.name.set('');
      this.email.set('');
      this.subject.set('');
      this.message.set('');
    }, 1200);
  }
}
