export interface AlertRecord {
  id: number;
  rule_id: string;
  patient_id: string;
  level: "INFO" | "WARNING" | "CRITICAL";
  status: string;
  title: string;
  message: string;
  metric_snapshot: Record<string, unknown>;
  created_at: string;
  acknowledged_at?: string | null;
  acknowledged_by?: string | null;
}

export interface LiveEvent {
  type: "vitals" | "alert" | "ack";
  patient_id: string;
  payload: any;
}
