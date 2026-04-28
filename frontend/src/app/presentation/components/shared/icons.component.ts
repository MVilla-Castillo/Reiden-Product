import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-icon',
  standalone: true,
  imports: [CommonModule],
  template: `
    <svg
      [attr.width]="size"
      [attr.height]="size"
      [attr.viewBox]="viewBox"
      [attr.fill]="fill"
      xmlns="http://www.w3.org/2000/svg"
      [class]="cssClass">
      @switch (name) {
        @case ('chart-bar') {
          <path stroke-linecap="round" stroke-linejoin="round" [attr.stroke-width]="strokeWidth" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
        }
        @case ('users') {
          <path stroke-linecap="round" stroke-linejoin="round" [attr.stroke-width]="strokeWidth" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"/>
        }
        @case ('chat-bubble-left-right') {
          <path stroke-linecap="round" stroke-linejoin="round" [attr.stroke-width]="strokeWidth" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/>
        }
        @case ('presentation-chart-line') {
          <path stroke-linecap="round" stroke-linejoin="round" [attr.stroke-width]="strokeWidth" d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z"/>
        }
        @case ('cog') {
          <path stroke-linecap="round" stroke-linejoin="round" [attr.stroke-width]="strokeWidth" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/>
          <path stroke-linecap="round" stroke-linejoin="round" [attr.stroke-width]="strokeWidth" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
        }
        @case ('user') {
          <path stroke-linecap="round" stroke-linejoin="round" [attr.stroke-width]="strokeWidth" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/>
        }
        @case ('bolt') {
          <path stroke-linecap="round" stroke-linejoin="round" [attr.stroke-width]="strokeWidth" d="M13 10V3L4 14h7v7l9-11h-7z"/>
        }
        @case ('exclamation-triangle') {
          <path stroke-linecap="round" stroke-linejoin="round" [attr.stroke-width]="strokeWidth" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
        }
        @case ('arrow-path') {
          <path stroke-linecap="round" stroke-linejoin="round" [attr.stroke-width]="strokeWidth" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9M20 20v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
        }
        @case ('briefcase') {
          <path stroke-linecap="round" stroke-linejoin="round" [attr.stroke-width]="strokeWidth" d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
        }
        @case ('target') {
          <path stroke-linecap="round" stroke-linejoin="round" [attr.stroke-width]="strokeWidth" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"/>
        }
        @case ('inbox') {
          <path stroke-linecap="round" stroke-linejoin="round" [attr.stroke-width]="strokeWidth" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"/>
        }
        @case ('trash') {
          <path stroke-linecap="round" stroke-linejoin="round" [attr.stroke-width]="strokeWidth" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h3m6 0h3"/>
        }
        @case ('document') {
          <path stroke-linecap="round" stroke-linejoin="round" [attr.stroke-width]="strokeWidth" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
        }
        @case ('chevron-down') {
          <path stroke-linecap="round" stroke-linejoin="round" [attr.stroke-width]="strokeWidth" d="M19 9l-7 7-7-7"/>
        }
        @case ('chevron-up') {
          <path stroke-linecap="round" stroke-linejoin="round" [attr.stroke-width]="strokeWidth" d="M5 15l7-7 7 7"/>
        }
        @case ('information-circle') {
          <path stroke-linecap="round" stroke-linejoin="round" [attr.stroke-width]="strokeWidth" d="M11 16.917A1 1 0 0112 16v-1.75a1 1 0 00-1-1h-1.75a1 1 0 00-1 1.75V16a1 1 0 001 1h1.75zM11.004 10A1.5 1.5 0 1011 7v3M11 17.5a1.5 1.5 0 100-3 1.5 1.5 0 000 3z"/>
        }
        @case ('calendar') {
          <path stroke-linecap="round" stroke-linejoin="round" [attr.stroke-width]="strokeWidth" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/>
        }
        @case ('clock') {
          <path stroke-linecap="round" stroke-linejoin="round" [attr.stroke-width]="strokeWidth" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
        }
        @case ('check-circle') {
          <path stroke-linecap="round" stroke-linejoin="round" [attr.stroke-width]="strokeWidth" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
        }
        @case ('user-group') {
          <path stroke-linecap="round" stroke-linejoin="round" [attr.stroke-width]="strokeWidth" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"/>
        }
        @case ('exclamation-circle') {
          <path stroke-linecap="round" stroke-linejoin="round" [attr.stroke-width]="strokeWidth" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
        }
        @default {
          <circle [attr.stroke-width]="strokeWidth" cx="12" cy="12" r="10"/>
        }
      }
    </svg>
  `,
  styles: [`
    :host {
      display: inline-flex;
    }
    svg {
      display: block;
    }
  `]
})
export class IconComponent {
  @Input() name: string = '';
  @Input() size: number = 24;
  @Input() strokeWidth: number = 1.5;
  @Input() fill: string = 'none';
  @Input() cssClass: string = '';

  get viewBox(): string {
    return '0 0 24 24';
  }
}