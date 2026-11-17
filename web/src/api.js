const BASE = import.meta.env.VITE_API_BASE ?? "";

export async function health() {
  const res = await fetch(`${BASE}/health`);
  return res.json();
}

export async function search(question, lang, topK = 5) {
  const res = await fetch(`${BASE}/api/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, lang, top_k: topK }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `HTTP ${res.status}`);
  }
  return res.json();
}
