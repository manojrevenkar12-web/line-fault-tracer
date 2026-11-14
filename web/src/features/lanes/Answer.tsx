export function Answer({ answer }: { answer?: { question: string; answer: string; sources: string[] } }) {
  if (!answer) return null;
  const [body] = answer.answer.split(" Sources: ");
  return (
    <figure className="answer">
      <blockquote className="question">{answer.question}</blockquote>
      <figcaption className="muted">An operator, at the alarm</figcaption>
      <p className="reply">{body}</p>
      <ul className="sources" aria-label="Sources quoted">
        {answer.sources.map((s) => (
          <li key={s}>{s}</li>
        ))}
      </ul>
    </figure>
  );
}
