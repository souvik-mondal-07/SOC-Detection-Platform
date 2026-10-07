import UnavailableState from "../components/common/UnavailableState";

export default function DetectionRulesPage() {
  return (
    <UnavailableState
      title="Detection rules cannot be listed yet."
      message="Rules are evaluated entirely by the backend, but it has no endpoint that returns them. Backend endpoint not available yet. Detection logic stays in the backend; this page will only display rule data it provides."
      plannedFields={["Rule ID", "Name", "Category", "Severity", "Enabled / disabled", "Conditions", "Threshold", "Time window"]}
    />
  );
}
