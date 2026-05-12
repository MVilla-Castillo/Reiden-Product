export type GuideTab = 'dashboard' | 'leads' | 'chat' | 'reports';
export type GuideRole = 'manager' | 'salesperson';
export type GuidePlacement = 'top' | 'bottom' | 'left' | 'right';

export interface GuideStep {
  id: string;
  selector: string;
  title: string;
  desc: string;
  placement: GuidePlacement;
}

export interface GuideResponse {
  tab: GuideTab;
  role: GuideRole;
  title: string;
  steps: GuideStep[];
}
