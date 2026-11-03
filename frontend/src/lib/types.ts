export interface User {
  id: string;
  email: string;
  full_name: string;
  role: "admin" | "analyst" | "viewer";
  is_active: boolean;
  org_id: string;
  org_name?: string | null;
  created_at: string;
}

export interface Dataset {
  id: string;
  name: string;
  original_filename: string;
  row_count: number;
  col_count: number;
  created_at: string;
  profile?: DatasetProfile;
}

export interface ColumnProfile {
  name: string;
  type: "numeric" | "datetime" | "categorical";
  nulls: number;
  unique: number;
  min?: number | string | null;
  max?: number | string | null;
  mean?: number | null;
  sum?: number | null;
  top_values?: { value: string; count: number }[];
}

export interface DatasetProfile {
  rows: number;
  cols: number;
  columns: ColumnProfile[];
  numeric_columns: string[];
  date_columns: string[];
  categorical_columns: string[];
}

export interface Kpis {
  row_count: number;
  column_count: number;
  primary_metric?: string | null;
  date_column?: string | null;
  metric_total?: number | null;
  metric_mean?: number | null;
  metric_max?: number | null;
  metric_min?: number | null;
  date_min?: string;
  date_max?: string;
  growth_first_last_pct?: number | null;
  best_month?: string;
  worst_month?: string;
}

export interface Insight {
  kind: string;
  title: string;
  body: string;
}

export interface ForecastPoint {
  period: string;
  value: number;
  lower: number;
  upper: number;
}

export interface ForecastResult {
  available: boolean;
  reason?: string;
  metric?: string;
  model?: string;
  mape_pct?: number | null;
  history?: { period: string; value: number }[];
  forecast?: ForecastPoint[];
}

export interface Report {
  id: string;
  dataset_id: string;
  title: string;
  created_at: string;
}

export interface AssistantAnswer {
  answer: string;
  narrative?: string | null;
  narrative_source: "ollama" | "builtin" | "none";
  chart?: any;
  table?: { rows: Record<string, any>[] } | null;
  computed?: Record<string, any> | null;
}

export interface AssistantConversation {
  id: string;
  dataset_id: string | null;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface AssistantChart {
  type: "bar" | "line" | string;
  items?: { label: string; value: number }[];
  points?: { period: string; value: number }[];
  [key: string]: unknown;
}

export interface AssistantAction {
  type?: string;
  kind?: string;
  action?: string;
  title?: string;
  dataset_id?: string | null;
  [key: string]: unknown;
}

export interface AssistantMessageMetadata {
  source?: string;
  dataset_id?: string | null;
  chart?: AssistantChart | null;
  table?: { rows: Record<string, unknown>[] } | null;
  computed?: Record<string, unknown> | null;
  actions?: AssistantAction[] | AssistantAction | string[] | string | null;
  tools?: unknown;
  [key: string]: unknown;
}

export interface AssistantMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  metadata: AssistantMessageMetadata | null;
  created_at: string;
}

export interface AssistantConversationDetail extends AssistantConversation {
  summary: string | null;
  messages: AssistantMessage[];
}

export interface AssistantContext {
  context_text: string;
  updated_at: string | null;
}
