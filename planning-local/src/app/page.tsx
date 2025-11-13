import Image from "next/image";

export default function Home() {
  return (
    <main className="p-6">
      <h1 className="text-2xl font-semibold">Planning local</h1>
      <a className="underline" href="/events/new">Créer un évènement</a>
    </main>
  );
}

