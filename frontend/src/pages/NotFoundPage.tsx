import { Link } from "react-router-dom";
import StateMessage from "../components/common/StateMessage";

export default function NotFoundPage() {
  return (
    <StateMessage variant="empty" title="Page not found">
      <Link to="/dashboard" className="font-medium text-cyan hover:underline">Go to the dashboard</Link>
    </StateMessage>
  );
}
