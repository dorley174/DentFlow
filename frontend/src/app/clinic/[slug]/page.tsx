import { ClinicApp } from "@/components/clinic-app";
export default async function ClinicPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  return <ClinicApp slug={slug} />;
}
