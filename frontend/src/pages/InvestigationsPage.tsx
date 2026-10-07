import UnavailableState from "../components/common/UnavailableState";

export default function InvestigationsPage() {
  return (
    <UnavailableState
      title="No investigations available."
      message="The backend does not expose investigation endpoints yet. Backend endpoint not available yet."
      plannedFields={["Investigation ID", "Title", "Status", "Linked alerts", "Notes"]}
    />
  );
}
