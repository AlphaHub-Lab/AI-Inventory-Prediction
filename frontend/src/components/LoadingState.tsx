export default function LoadingState({ label = 'Loading…', className = '' }: { label?: string; className?: string }) {
  return (
    <div className={`page-loading ${className}`.trim()} role="status" aria-live="polite">
      <span className="page-loading-spinner" aria-hidden="true" />
      <span>{label}</span>
    </div>
  )
}
