export default function SettingsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-[var(--background)]">
      {/* 100% width, top-aligned, responsive width control */}
      <div className="w-full">
        {children}
      </div>
    </div>
  );
}