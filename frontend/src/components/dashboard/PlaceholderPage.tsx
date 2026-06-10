import { PageHeader } from "./PageHeader";

export function PlaceholderPage({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children?: React.ReactNode;
}) {
  return (
    <div>
      <PageHeader title={title} subtitle={subtitle} />
      <div className="space-y-4">{children}</div>
    </div>
  );
}