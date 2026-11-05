export type Row = { id: string; [key: string]: unknown };
export type User = {
  id: string;
  name: string;
  email: string;
  role: string;
  tenant_id?: string;
};
export type Tenant = Row & {
  name: string;
  slug: string;
  status?: string;
  brand_color?: string;
  phone?: string;
  description?: string;
  timezone?: string;
  plan?: string;
};
export type Branch = Row & { name: string; address: string; phone?: string };
export type Service = Row & {
  name: string;
  category: string;
  duration_minutes: number;
  price_kopecks: number;
  active: boolean;
};
export type Doctor = Row & {
  name: string;
  specialty: string;
  branch_id: string;
  color?: string;
  active: boolean;
  service_ids: string[];
};
export type Patient = Row & {
  name: string;
  phone: string;
  segment: string;
  notifications_enabled?: boolean;
  created_at?: string;
};
export type Appointment = Row & {
  patient_id: string;
  patient_name: string;
  doctor_id: string;
  doctor_name: string;
  service_id: string;
  service_name: string;
  branch_id: string;
  branch_name: string;
  start_at: string;
  end_at: string;
  status: string;
  price_kopecks: number;
  source: string;
};
export type Lead = Row & {
  patient_id?: string;
  patient_name?: string;
  title: string;
  stage: string;
  source: string;
  summary?: string;
  assigned_to?: string;
  amount_kopecks: number;
};
export type Task = Row & {
  title: string;
  description?: string;
  status: string;
  due_at?: string;
  assigned_to?: string;
  patient_id?: string;
};
export type Conversation = Row & {
  patient_id?: string;
  patient_name?: string;
  channel: string;
  mode: string;
  status: string;
  last_message?: string;
  updated_at?: string;
};
export type Message = Row & { role: string; text: string; created_at?: string };
export type ChatOption = {
  label: string;
  action: string;
  data?: Record<string, unknown>;
};
export type ChatState = {
  conversation?: Conversation;
  messages: Message[];
  options?: ChatOption[];
  appointment?: Appointment;
};
export type Slot = {
  start_at: string;
  end_at: string;
  doctor_id: string;
  doctor_name?: string;
  branch_id: string;
};
export type ClinicData = {
  tenant: Tenant;
  branches: Branch[];
  doctors: Doctor[];
  services: Service[];
};
export type Config = {
  environment: string;
  dev_tools: boolean;
  plans: (Row & {
    code: string;
    name: string;
    price_kopecks: number;
    features?: string[];
  })[];
};
export type Bootstrap = ClinicData & {
  user: User;
  patients: Patient[];
  appointments: Appointment[];
  leads: Lead[];
  conversations: Conversation[];
  tasks: Task[];
  notifications: Row[];
  automation_rules: Row[];
  integrations: Row[];
  ai_settings: Record<string, unknown>;
  staff: Row[];
  schedules?: Row[];
  metrics: Record<string, number>;
  audit_logs: Row[];
};
