export interface HealthResponse {
  status: string;
  message: string;
  service: string;
  version: string;
  environment: string;
  timestamp: string;
}
