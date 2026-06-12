interface EmptyStateProps {
  text: string;
  className?: string;
}

export default function EmptyState({ text, className = '' }: EmptyStateProps) {
  return <p className={`text-gray-500 ${className}`.trim()}>{text}</p>;
}
