import StateMessage from "./StateMessage";

/** Error message with a retry button. */
export default function ErrorState({ title, message, onRetry }: { title: string; message: string; onRetry: () => void }) {
  return (
    <StateMessage variant="error" title={title}>
      {message}
      <div className="mt-3">
        <button type="button" onClick={onRetry} className="btn">
          Try again
        </button>
      </div>
    </StateMessage>
  );
}
