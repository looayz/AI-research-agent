export function Logo({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden>
      <rect width="32" height="32" rx="8" fill="currentColor" className="text-sidebar-fg" />
      <circle cx="14" cy="14" r="6.5" fill="none" stroke="rgb(var(--sidebar))" strokeWidth="2.4" />
      <path d="M19 19l5.5 5.5" stroke="rgb(var(--sidebar))" strokeWidth="2.6" strokeLinecap="round" />
      <path d="M11 14.2l2 2 4-4.4" fill="none" stroke="rgb(var(--sidebar))" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
