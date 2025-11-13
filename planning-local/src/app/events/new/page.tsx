"use client";
import { useState } from "react";
import { api } from "@/lib/api";


export default function NewEvent() {
  const [title, setTitle] = useState("");
  const [desc, setDesc] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const ev = await api<{id:string}>("/api/events", {
      method: "POST",
      body: JSON.stringify({ title, description: desc })
    });
    window.location.href = `/events/${ev.id}`;
  }

  return (
    <form onSubmit={submit} className="p-6 space-y-3">
      <input className="border p-2 w-full" placeholder="Titre" value={title} onChange={e=>setTitle(e.target.value)} />
      <textarea className="border p-2 w-full" placeholder="Description" value={desc} onChange={e=>setDesc(e.target.value)} />
      <button className="bg-black text-white px-4 py-2 rounded">Créer</button>
    </form>
  );
}
