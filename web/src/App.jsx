import { useEffect, useState } from "react";
import { health, search } from "./api.js";

const COPY = {
  en: {
    title: "EU-Law Assistant",
    subtitle: "Ask about the AI Act, the GDPR or the Data Act. Answers cite the exact article.",
    placeholder: "Which AI practices are prohibited?",
    button: "Search sources",
    generating: "Answer generation lands in Week 1.",
    sources: "Retrieved sources",
    empty: "No sources yet — ingest the corpus first.",
  },
  fr: {
    title: "Assistant Droit UE",
    subtitle: "Interrogez l'AI Act, le RGPD ou le Data Act. Les réponses citent l'article exact.",
    placeholder: "Quelles pratiques d'IA sont interdites ?",
    button: "Chercher les sources",
    generating: "La génération de réponse arrive en semaine 1.",
    sources: "Sources retrouvées",
    empty: "Aucune source — lancez d'abord l'ingestion.",
  },
};

export default function App() {
  const [lang, setLang] = useState("en");
  const [question, setQuestion] = useState("");
  const [hits, setHits] = useState(null);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("…");
  const t = COPY[lang];

  useEffect(() => {
    health()
      .then((h) => setStatus(h.db === "ok" ? "API + DB ready" : "API up, DB unavailable"))
      .catch(() => setStatus("API offline"));
  }, []);

  async function onSubmit(event) {
    event.preventDefault();
    setError("");
    setHits(null);
    try {
      setHits(await search(question, lang, 5));
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <main className="shell">
      <header>
        <h1>{t.title}</h1>
        <p className="subtitle">{t.subtitle}</p>
        <div className="row">
          <span className={`dot ${status.includes("ready") ? "ok" : "warn"}`} />
          <span className="status">{status}</span>
          <button className="ghost" onClick={() => setLang(lang === "en" ? "fr" : "en")}>
            {lang === "en" ? "FR" : "EN"}
          </button>
        </div>
      </header>

      <form onSubmit={onSubmit} className="ask">
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={t.placeholder}
          rows={3}
        />
        <button type="submit" disabled={question.trim().length < 3}>
          {t.button}
        </button>
      </form>

      {error && <p className="error">{error}</p>}

      {hits && (
        <section>
          <h2>{t.sources}</h2>
          {hits.length === 0 && <p className="muted">{t.empty}</p>}
          <ul className="hits">
            {hits.map((hit) => (
              <li key={hit.chunk_id}>
                <div className="hit-head">
                  <strong>{hit.heading_path}</strong>
                  <span className="score">{hit.score.toFixed(3)}</span>
                </div>
                <p>{hit.content}</p>
              </li>
            ))}
          </ul>
        </section>
      )}

      <footer className="muted">{t.generating}</footer>
    </main>
  );
}
