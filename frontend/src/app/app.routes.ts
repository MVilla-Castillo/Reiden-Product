import { Routes } from '@angular/router';
import { LoginComponent } from './features/auth/login/login.component';

import { ManagerDashboardComponent } from './features/dashboard/manager-dashboard/manager-dashboard.component';
import { AgentDashboardComponent } from './features/dashboard/agent-dashboard/agent-dashboard.component';

export const routes: Routes = [
  { path: '', redirectTo: 'login', pathMatch: 'full' },
  { path: 'login', component: LoginComponent },
  { path: 'dashboard', component: ManagerDashboardComponent },
  { path: 'vendedor', component: AgentDashboardComponent }
];
