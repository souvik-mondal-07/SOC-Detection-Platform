export interface HealthResponse {
  status: string;
  message: string;
  service: string;
  version: string;
  environment: string;
  database: "connected" | "unavailable";
  timestamp: string;
}
