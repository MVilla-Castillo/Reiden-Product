import { Routes } from '@angular/router';
import { DashboardComponent } from './presentation/pages/dashboard/dashboard.component';
import { ChatComponent } from './presentation/pages/chat/chat.component';
import { LoginComponent } from './presentation/pages/login/login.component';
import { LandingComponent } from './presentation/pages/landing/landing.component';
import { LeadsComponent } from './presentation/pages/leads/leads.component';
import { ReportsComponent } from './presentation/pages/reports/reports.component';
import { SettingsComponent } from './presentation/pages/settings/settings.component';
import { ProfileComponent } from './presentation/pages/profile/profile.component';
import { authGuard } from './core/guards/auth.guard';

export const routes: Routes = [
  { path: '', component: LandingComponent },
  { path: 'login', component: LoginComponent },
  { 
    path: 'dashboard', 
    component: DashboardComponent, 
    canActivate: [authGuard], 
    data: { role: 'manager' } 
  },
  {
    path: 'leads',
    component: LeadsComponent,
    canActivate: [authGuard]
  },
  { 
    path: 'reports', 
    component: ReportsComponent, 
    canActivate: [authGuard], 
    data: { role: 'manager' } 
  },
  { 
    path: 'chat', 
    component: ChatComponent, 
    canActivate: [authGuard]
    // Sales can enter chat, Manager can too for view/override purposes
  },
  { 
    path: 'settings', 
    component: SettingsComponent, 
    canActivate: [authGuard]
  },
  { 
    path: 'profile', 
    component: ProfileComponent, 
    canActivate: [authGuard]
  },
];
