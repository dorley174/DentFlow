import { ChatPanel } from "@/components/chat";
export default async function WidgetPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  return (
    <main className="widget-page">
      <ChatPanel slug={slug} />
      <a
        className="widget-link"
        href={`/clinic/${encodeURIComponent(slug)}`}
        target="_blank"
        rel="noreferrer"
      >
        Открыть сайт клиники в отдельной вкладке
      </a>
    </main>
  );
}
