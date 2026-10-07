import UnavailableState from "../components/common/UnavailableState";

export default function AlertsPage() {
  return (
    <UnavailableState
      title="Alert management is not available yet."
      message="The backend does not expose alert endpoints. Detection results are not alerts and nothing is stored when rules match, so there is nothing to list here."
      plannedFields={["Alert ID", "Rule", "Severity", "Status", "Source IP", "Related events", "Created"]}
    />
  );
}
