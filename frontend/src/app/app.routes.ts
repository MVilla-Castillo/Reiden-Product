import { Routes } from '@angular/router';
import { DashboardComponent } from './presentation/pages/dashboard/dashboard.component';
import { ChatComponent } from './presentation/pages/chat/chat.component';
import { LoginComponent } from './presentation/pages/login/login.component';
import { authGuard } from './core/guards/auth.guard';

export const routes: Routes = [
  { path: 'login', component: LoginComponent },
  { path: '', redirectTo: 'login', pathMatch: 'full' },
  { 
    path: 'dashboard', 
    component: DashboardComponent, 
    canActivate: [authGuard], 
    data: { role: 'manager' } 
  },
  { 
    path: 'chat', 
    component: ChatComponent, 
    canActivate: [authGuard], 
    data: { role: 'sales' } 
  },
];