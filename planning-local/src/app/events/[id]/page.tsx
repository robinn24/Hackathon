import { API } from "@/lib/api";

async function getEvent(id: string) {
  const res = await fetch(`${API}/api/events/${id}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Not found");
  return res.json();
}

export default async function EventPage({ params }: { params: { id: string }}) {
  const event = await getEvent(params.id);
  return (
    <main className="p-6">
      <h1 className="text-xl font-semibold">{event.title}</h1>
      <p className="text-gray-600">{event.description}</p>
      {/* TODO: slots + réponses */}
    </main>
  );
}
