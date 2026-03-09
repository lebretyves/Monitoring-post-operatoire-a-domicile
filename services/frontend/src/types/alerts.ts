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

export interface NotificationRecord {
  id: number;
  patient_id: string;
  alert_id?: number | null;
  level: "INFO" | "WARNING" | "CRITICAL";
  status: "UNREAD" | "READ";
  channel: string;
  title: string;
  message: string;
  payload: Record<string, unknown>;
  created_at: string;
  read_at?: string | null;
  read_by?: string | null;
}

export interface LiveEvent {
  type: "vitals" | "alert" | "ack" | "notification" | "notification_read" | "notifications_reset";
  patient_id: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  payload: any;
}
