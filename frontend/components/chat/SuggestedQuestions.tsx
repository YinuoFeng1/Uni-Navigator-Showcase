import { suggestedQuestions } from "@/lib/mockData";

type SuggestedQuestionsProps = {
  onSelect: (question: string) => void;
  disabled?: boolean;
};

export function SuggestedQuestions({
  onSelect,
  disabled = false,
}: SuggestedQuestionsProps) {
  return (
    <div className="flex flex-wrap gap-2" aria-label="Suggested questions">
      {suggestedQuestions.map((question) => (
        <button
          key={question}
          type="button"
          className="rounded-full border border-[var(--border-light)] bg-white px-4 py-2 text-left text-sm font-bold text-[var(--uq-purple)] transition hover:bg-[var(--uq-purple-light)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 disabled:pointer-events-none disabled:opacity-50"
          onClick={() => onSelect(question)}
          disabled={disabled}
        >
          {question}
        </button>
      ))}
    </div>
  );
}
